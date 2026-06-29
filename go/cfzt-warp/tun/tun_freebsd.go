//go:build freebsd

package tun

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"

	"github.com/songgao/water"
)

// FreeBSDTUN manages a TUN interface on FreeBSD using /dev/tunN devices.
type FreeBSDTUN struct {
	iface  *water.Interface
	name   string
	mtu    int
}

// New creates and configures a new TUN interface for MASQUE traffic.
//
// FreeBSD TUN devices are pre-allocated at /dev/tun0, /dev/tun1, etc.
// The water library opens the first available /dev/tunN device.
// We then configure it with ifconfig.
func New(clientIPv4, clientIPv6 string, mtu int) (*FreeBSDTUN, error) {
	cfg := water.Config{DeviceType: water.TUN}
	iface, err := water.New(cfg)
	if err != nil {
		return nil, fmt.Errorf("failed to create TUN device: %w", err)
	}

	name := iface.Name()

	// Set MTU
	if err := exec.Command("ifconfig", name, "mtu", fmt.Sprintf("%d", mtu)).Run(); err != nil {
		_ = iface.Close()
		return nil, fmt.Errorf("failed to set MTU on %s: %w", name, err)
	}

	// Assign IPv4 address if provided
	if clientIPv4 != "" {
		// clientIPv4 may be "100.96.x.y/10" — parse out address and prefix
		ip, ipNet, err := net.ParseCIDR(clientIPv4)
		if err != nil {
			// Try as plain address with /32
			ip = net.ParseIP(clientIPv4)
			_, ipNet, _ = net.ParseCIDR(clientIPv4 + "/32")
		}
		if ip != nil && ipNet != nil {
			mask := ipNet.Mask
			netmask := fmt.Sprintf("%d.%d.%d.%d", mask[0], mask[1], mask[2], mask[3])
			// FreeBSD ifconfig: ifconfig tunN inet <addr> <dest> netmask <mask>
			// For point-to-point TUN, destination is same as address
			if err := exec.Command("ifconfig", name, "inet",
				ip.String(), ip.String(), "netmask", netmask).Run(); err != nil {
				_ = iface.Close()
				return nil, fmt.Errorf("failed to set IPv4 on %s: %w", name, err)
			}
		}
	}

	// Assign IPv6 address if provided
	if clientIPv6 != "" {
		ip6, ip6Net, err := net.ParseCIDR(clientIPv6)
		if err != nil {
			ip6 = net.ParseIP(clientIPv6)
		}
		if ip6 != nil {
			prefixLen := 128
			if ip6Net != nil {
				ones, _ := ip6Net.Mask.Size()
				prefixLen = ones
			}
			if err := exec.Command("ifconfig", name, "inet6",
				fmt.Sprintf("%s/%d", ip6.String(), prefixLen), "alias").Run(); err != nil {
				// Non-fatal: IPv6 may not be needed
				_ = err
			}
		}
	}

	// Bring interface up
	if err := exec.Command("ifconfig", name, "up").Run(); err != nil {
		_ = iface.Close()
		return nil, fmt.Errorf("failed to bring up %s: %w", name, err)
	}

	return &FreeBSDTUN{iface: iface, name: name, mtu: mtu}, nil
}

func (t *FreeBSDTUN) Name() string { return t.name }
func (t *FreeBSDTUN) MTU() int     { return t.mtu }

func (t *FreeBSDTUN) Read(buf []byte) (int, error) {
	return t.iface.Read(buf)
}

func (t *FreeBSDTUN) Write(buf []byte) error {
	_, err := t.iface.Write(buf)
	return err
}

func (t *FreeBSDTUN) Close() error {
	_ = exec.Command("ifconfig", t.name, "down").Run()
	return t.iface.Close()
}

// AddRoute adds a route through this TUN interface.
func (t *FreeBSDTUN) AddRoute(prefix string) error {
	// route add -net <prefix> -interface <tun>
	return exec.Command("route", "add", "-net", prefix, "-interface", t.name).Run()
}

// DelRoute removes a route through this TUN interface.
func (t *FreeBSDTUN) DelRoute(prefix string) error {
	return exec.Command("route", "delete", "-net", prefix, "-interface", t.name).Run()
}

// AddDefaultRoute sets this interface as the default route (full tunnel mode).
// Preserves management routes to avoid losing SSH access.
func (t *FreeBSDTUN) AddDefaultRoute(gatewayToPreserve string) error {
	// Add specific host routes for Cloudflare WARP endpoints before changing default
	cloudflareEndpoints := []string{"162.159.198.1", "162.159.198.2", "162.159.198.0/24"}
	for _, ep := range cloudflareEndpoints {
		_ = exec.Command("route", "add", "-net", ep, gatewayToPreserve).Run()
	}
	// Set default route via TUN
	if err := exec.Command("route", "change", "default", "-interface", t.name).Run(); err != nil {
		return exec.Command("route", "add", "default", "-interface", t.name).Run()
	}
	return nil
}

// WriteIfaceStateFile writes the interface name to a state file so monitor.py can find it.
func (t *FreeBSDTUN) WriteIfaceStateFile(connUUID string) error {
	path := "/var/run/cfzt-iface-" + connUUID
	return os.WriteFile(path, []byte(t.name), 0644)
}

// RemoveIfaceStateFile removes the state file on shutdown.
func (t *FreeBSDTUN) RemoveIfaceStateFile(connUUID string) {
	_ = os.Remove("/var/run/cfzt-iface-" + connUUID)
}

// ApplySplitTunnelRules applies split tunnel include/exclude routes.
// excludes: bypass the tunnel (use normal routing)
// includes: force through the tunnel
func (t *FreeBSDTUN) ApplySplitTunnelRules(includes, excludes []string, defaultGW string) error {
	var errs []string
	for _, prefix := range includes {
		if err := t.AddRoute(prefix); err != nil {
			errs = append(errs, fmt.Sprintf("include %s: %v", prefix, err))
		}
	}
	for _, prefix := range excludes {
		// Route exclusions via the original gateway (bypass tunnel)
		if err := exec.Command("route", "add", "-net", prefix, defaultGW).Run(); err != nil {
			errs = append(errs, fmt.Sprintf("exclude %s: %v", prefix, err))
		}
	}
	if len(errs) > 0 {
		return fmt.Errorf("route errors: %s", strings.Join(errs, "; "))
	}
	return nil
}
