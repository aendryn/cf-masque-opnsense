package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"log/syslog"
	"os"
	"os/exec"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/opnsense/cloudflare-zt/cfzt-warp/daemon"
	"github.com/opnsense/cloudflare-zt/cfzt-warp/models"
	"github.com/opnsense/cloudflare-zt/cfzt-warp/tun"
)

// Version is set at build time via -ldflags.
var Version = "dev"

func main() {
	configPath := flag.String("config", "", "Path to JSON connection config (required)")
	asDaemon := flag.Bool("daemon", false, "Daemonize (write PID file and detach)")
	showVersion := flag.Bool("version", false, "Print version and exit")
	flag.Parse()

	if *showVersion {
		fmt.Printf("cfzt-warp %s\n", Version)
		os.Exit(0)
	}
	if *configPath == "" {
		fmt.Fprintln(os.Stderr, "cfzt-warp: --config is required")
		os.Exit(1)
	}

	cfg, err := loadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "cfzt-warp: load config: %v\n", err)
		os.Exit(1)
	}

	// Set up syslog output
	ident := cfg.LogIdent
	if ident == "" {
		ident = "cfzt-warp"
	}
	syslogWriter, err := syslog.New(syslog.LOG_DAEMON|syslog.LOG_INFO, ident)
	if err == nil {
		log.SetOutput(syslogWriter)
		log.SetFlags(0)
	}

	if *asDaemon {
		if err := daemonize(cfg.PIDFile); err != nil {
			log.Fatalf("daemonize: %v", err)
		}
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT, syscall.SIGHUP)
	go func() {
		for sig := range sigCh {
			if sig == syscall.SIGHUP {
				log.Println("SIGHUP received — config reload not yet supported, ignoring")
				continue
			}
			log.Printf("Signal %v received, shutting down", sig)
			cancel()
			return
		}
	}()

	switch cfg.Protocol {
	case "warp_masque":
		runMASQUE(ctx, cfg)
	case "warp_wireguard":
		runWireGuard(ctx, cfg)
	default:
		log.Fatalf("Unknown protocol: %s", cfg.Protocol)
	}

	log.Println("cfzt-warp stopped")
	if cfg.PIDFile != "" {
		_ = os.Remove(cfg.PIDFile)
	}
}

func runMASQUE(ctx context.Context, cfg *models.DaemonConfig) {
	if cfg.MasquePrivateKey == "" || cfg.MasqueCertDER == "" {
		log.Fatal("MASQUE private key and certificate are required (run register/enroll first)")
	}

	tunDev, err := tun.New(cfg.ClientIPv4, cfg.ClientIPv6, "cfzt"+shortUUID(cfg.ConnectionUUID), cfg.MTU)
	if err != nil {
		log.Fatalf("Create TUN: %v", err)
	}
	defer tunDev.Close()

	log.Printf("TUN interface %s up (IPv4=%s IPv6=%s MTU=%d)",
		tunDev.Name(), cfg.ClientIPv4, cfg.ClientIPv6, cfg.MTU)

	if err := tunDev.WriteIfaceStateFile(cfg.ConnectionUUID); err != nil {
		log.Printf("Warning: could not write interface state file: %v", err)
	}
	defer tunDev.RemoveIfaceStateFile(cfg.ConnectionUUID)

	// Apply routing based on tunnel mode
	// Full tunnel: default route via TUN
	// Split tunnel: routes managed by split tunnel rules (applied separately)
	if cfg.TunnelMode == "full" {
		gw := defaultGateway()
		if err := tunDev.AddDefaultRoute(gw); err != nil {
			log.Printf("Warning: add default route: %v", err)
		}
		// Restore original default route when tunnel exits (runs before Close()).
		// Without this, stopping the tunnel removes the default route and the
		// box loses all connectivity until manually fixed.
		if gw != "" {
			defer func() {
				log.Printf("Restoring default route via %s", gw)
				if err := exec.Command("route", "change", "default", gw).Run(); err != nil {
					_ = exec.Command("route", "add", "default", gw).Run()
				}
			}()

			// In system DNS mode Unbound forwards to upstream servers configured in
			// OPNsense. Those servers need direct (pre-tunnel) routes so DNS queries
			// don't enter the tunnel and silently fail.
			if cfg.DNSMode == "system" {
				for _, srv := range opnsenseDNSServers() {
					if err := exec.Command("route", "add", "-host", srv, gw).Run(); err != nil {
						log.Printf("Warning: DNS host route %s via %s: %v", srv, gw, err)
						continue
					}
					log.Printf("Added DNS host route: %s via %s", srv, gw)
					srv := srv // capture loop var for defer
					defer func() {
						_ = exec.Command("route", "delete", "-host", srv).Run()
						log.Printf("Removed DNS host route: %s", srv)
					}()
				}
			}
		}
	}

	maintCfg := daemon.MaintainConfig{
		TLSPrivKeyDERb64:  cfg.MasquePrivateKey,
		TLSCertDERb64:     cfg.MasqueCertDER,
		EndpointPubkeyPEM: cfg.EndpointPubkey,
		EndpointV4:        cfg.EndpointV4,
		EndpointV6:        cfg.EndpointV6,
		UseIPv6:           cfg.UseIPv6,
		UseH2:             false, // Start with QUIC
		MTU:               cfg.MTU,
		ReconnectDelay:    time.Duration(cfg.ReconnectDelay) * time.Second,
		AlwaysReconnect:   cfg.AlwaysReconnect,
		Device:            tunDev,
		ConnUUID:          cfg.ConnectionUUID,
	}

	daemon.MaintainTunnel(ctx, maintCfg)
}

func runWireGuard(ctx context.Context, cfg *models.DaemonConfig) {
	if cfg.WgPrivateKey == "" {
		log.Fatal("WireGuard private key is required")
	}

	ifname := "cfzt" + shortUUID(cfg.ConnectionUUID)

	// FreeBSD 14+ ifconfig has native WireGuard support (wgkey, wgpeer, wgendpoint, wgaip)
	// — no wireguard-tools package needed.
	cmds := [][]string{
		{"ifconfig", "wg", "create", "name", ifname},
		{"ifconfig", ifname, "wgkey", cfg.WgPrivateKey},
		{"ifconfig", ifname,
			"wgpeer", cfg.WgPeerPubkey,
			"wgendpoint", cfg.EndpointV4, strconv.Itoa(cfg.WgPeerPort),
			"wgaip", "0.0.0.0/0",
			"wgaip", "::/0"},
		{"ifconfig", ifname, "inet", cfg.ClientIPv4, cfg.ClientIPv4},
		{"ifconfig", ifname, "mtu", strconv.Itoa(cfg.MTU)},
		{"ifconfig", ifname, "up"},
	}

	for _, args := range cmds {
		if out, err := exec.CommandContext(ctx, args[0], args[1:]...).CombinedOutput(); err != nil {
			log.Fatalf("WireGuard setup %v: %v (%s)", args, err, out)
		}
	}

	_ = os.WriteFile("/var/run/cfzt-iface-"+cfg.ConnectionUUID, []byte(ifname), 0644)
	defer os.Remove("/var/run/cfzt-iface-" + cfg.ConnectionUUID)

	log.Printf("WireGuard interface %s up (peer=%s)", ifname, cfg.WgPeerPubkey)
	<-ctx.Done()

	_ = exec.Command("ifconfig", ifname, "destroy").Run()
	log.Printf("WireGuard interface %s destroyed", ifname)
}

func loadConfig(path string) (*models.DaemonConfig, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var cfg models.DaemonConfig
	if err := json.NewDecoder(f).Decode(&cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}

// daemonize writes the PID file. On FreeBSD we don't fork (use daemon(8) wrapper or
// rely on OPNsense configd which manages the process). We just write the PID file.
func daemonize(pidFile string) error {
	if pidFile == "" {
		return nil
	}
	pid := os.Getpid()
	return os.WriteFile(pidFile, []byte(strconv.Itoa(pid)+"\n"), 0644)
}

func defaultGateway() string {
	out, err := exec.Command("route", "-n", "get", "default").Output()
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "gateway:") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				return parts[1]
			}
		}
	}
	return ""
}

// opnsenseDNSServers returns the upstream DNS servers from OPNsense's config.xml.
func opnsenseDNSServers() []string {
	data, err := os.ReadFile("/conf/config.xml")
	if err != nil {
		return nil
	}
	var servers []string
	const open, close = "<dnsserver>", "</dnsserver>"
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, open) && strings.HasSuffix(line, close) {
			ip := strings.TrimSpace(line[len(open) : len(line)-len(close)])
			if ip != "" {
				servers = append(servers, ip)
			}
		}
	}
	return servers
}

// shortUUID returns a short numeric suffix derived from a UUID for interface naming.
// FreeBSD interface names are limited to IFNAMSIZ-1 (15) characters.
func shortUUID(uuid string) string {
	// Use last 4 hex chars of UUID as interface index; keep it short
	clean := strings.ReplaceAll(uuid, "-", "")
	if len(clean) >= 4 {
		// Convert last 4 hex chars to decimal 0-65535
		n, err := strconv.ParseUint(clean[len(clean)-4:], 16, 16)
		if err == nil {
			return strconv.FormatUint(n, 10)
		}
	}
	return "0"
}
