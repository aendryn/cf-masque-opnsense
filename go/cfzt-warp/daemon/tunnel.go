package daemon

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"sync"
	"time"

	connectip "github.com/Diniboy1123/connect-ip-go"

	"github.com/opnsense/cloudflare-zt/cfzt-warp/api"
	"github.com/opnsense/cloudflare-zt/cfzt-warp/internal"
)

// TunnelDevice abstracts a TUN interface for packet I/O.
type TunnelDevice interface {
	Read(buf []byte) (int, error)
	Write(buf []byte) error
}

// MaintainConfig holds runtime settings for the MASQUE tunnel loop.
type MaintainConfig struct {
	TLSPrivKeyDERb64  string
	TLSCertDERb64     string
	EndpointPubkeyPEM string
	EndpointV4        string
	EndpointV6        string
	UseIPv6           bool
	UseH2             bool
	MTU               int
	ReconnectDelay    time.Duration
	AlwaysReconnect   bool
	Device            TunnelDevice
	ConnUUID          string // for logging
}

const pumpShutdownGrace = 2 * time.Second

// MaintainTunnel runs the MASQUE connection loop until ctx is cancelled.
// It connects, pumps packets, reconnects on failure, respects backoff.
func MaintainTunnel(ctx context.Context, cfg MaintainConfig) {
	sni := internal.MasqueSNIZeroTrust
	tlsCfg, err := api.TLSConfig(cfg.TLSPrivKeyDERb64, cfg.TLSCertDERb64, cfg.EndpointPubkeyPEM, sni)
	if err != nil {
		log.Fatalf("TLS config: %v", err)
	}

	bufPool := newBufPool(cfg.MTU + internal.DatagramContextIDHeadroom)
	delay := cfg.ReconnectDelay

	for {
		if ctx.Err() != nil {
			return
		}

		if !cfg.AlwaysReconnect {
			// Wait for outbound activity before connecting
			buf := bufPool.get()
			n, err := cfg.Device.Read(buf[internal.DatagramContextIDHeadroom:])
			bufPool.put(buf)
			if err != nil {
				log.Printf("[%s] TUN read while idle: %v", cfg.ConnUUID[:8], err)
				if sleepCtx(ctx, delay) != nil {
					return
				}
				continue
			}
			log.Printf("[%s] Outbound activity (%d bytes), connecting...", cfg.ConnUUID[:8], n)
		}

		endpoint, err := cfg.selectEndpoint()
		if err != nil {
			log.Printf("[%s] Endpoint selection failed: %v", cfg.ConnUUID[:8], err)
			if sleepCtx(ctx, delay) != nil {
				return
			}
			continue
		}

		log.Printf("[%s] Connecting to MASQUE endpoint %s (H2=%v)", cfg.ConnUUID[:8], endpoint, cfg.UseH2)
		result, rsp, err := api.ConnectMASQUE(ctx, tlsCfg, endpoint, cfg.UseH2)
		if err != nil {
			log.Printf("[%s] MASQUE connect failed: %v", cfg.ConnUUID[:8], err)
			delay = backoff(delay, cfg.ReconnectDelay, 60*time.Second)
			if sleepCtx(ctx, delay) != nil {
				return
			}
			continue
		}
		if rsp.StatusCode != 200 {
			log.Printf("[%s] MASQUE connect HTTP %s", cfg.ConnUUID[:8], rsp.Status)
			_ = result.IPConn.Close()
			closeResult(result)
			delay = backoff(delay, cfg.ReconnectDelay, 60*time.Second)
			if sleepCtx(ctx, delay) != nil {
				return
			}
			continue
		}

		log.Printf("[%s] MASQUE tunnel connected", cfg.ConnUUID[:8])
		delay = cfg.ReconnectDelay // reset on success

		errCh := make(chan error, 2)
		pumpCtx, cancelPumps := context.WithCancel(ctx)
		var wg sync.WaitGroup
		var readMu sync.Mutex
		wg.Add(2)

		// TUN → MASQUE
		go func() {
			defer wg.Done()
			for {
				if pumpCtx.Err() != nil {
					return
				}
				buf := bufPool.get()
				readMu.Lock()
				n, err := cfg.Device.Read(buf[internal.DatagramContextIDHeadroom:])
				readMu.Unlock()
				if err != nil {
					bufPool.put(buf)
					errCh <- fmt.Errorf("TUN read: %w", err)
					return
				}
				if pumpCtx.Err() != nil {
					bufPool.put(buf)
					return
				}
				icmp, err := result.IPConn.WritePacketBuffer(buf, internal.DatagramContextIDHeadroom, n)
				bufPool.put(buf)
				if err != nil {
					if errors.As(err, new(*connectip.CloseError)) {
						errCh <- fmt.Errorf("MASQUE write closed: %w", err)
						return
					}
					log.Printf("[%s] MASQUE write: %v", cfg.ConnUUID[:8], err)
					continue
				}
				if len(icmp) > 0 {
					if err := cfg.Device.Write(icmp); err != nil {
						log.Printf("[%s] TUN write ICMP: %v", cfg.ConnUUID[:8], err)
					}
				}
			}
		}()

		// MASQUE → TUN
		go func() {
			defer wg.Done()
			for {
				pkt, err := result.IPConn.ReadPacketZeroCopy(true)
				if err != nil {
					if errors.As(err, new(*connectip.CloseError)) {
						errCh <- fmt.Errorf("MASQUE read closed: %w", err)
						return
					}
					log.Printf("[%s] MASQUE read: %v", cfg.ConnUUID[:8], err)
					if cfg.UseH2 {
						errCh <- err
						return
					}
					continue
				}
				if err := cfg.Device.Write(pkt); err != nil {
					errCh <- fmt.Errorf("TUN write: %w", err)
					return
				}
			}
		}()

		pumpErr := <-errCh
		log.Printf("[%s] Tunnel lost: %v — reconnecting in %s", cfg.ConnUUID[:8], pumpErr, delay)

		cancelPumps()
		_ = result.IPConn.Close()

		done := make(chan struct{})
		go func() { wg.Wait(); close(done) }()
		select {
		case <-done:
		case <-time.After(pumpShutdownGrace):
			log.Printf("[%s] Pump shutdown grace expired", cfg.ConnUUID[:8])
		}
		closeResult(result)

		if sleepCtx(ctx, delay) != nil {
			return
		}
		delay = backoff(delay, cfg.ReconnectDelay, 60*time.Second)
	}
}

func (cfg *MaintainConfig) selectEndpoint() (net.Addr, error) {
	if cfg.UseH2 {
		ip := net.ParseIP(internal.WARPH2EndpointV4)
		if ip == nil {
			return nil, fmt.Errorf("invalid H2 endpoint IP %q", internal.WARPH2EndpointV4)
		}
		return &net.TCPAddr{IP: ip, Port: internal.WARPH2Port}, nil
	}
	epStr := cfg.EndpointV4
	if cfg.UseIPv6 && cfg.EndpointV6 != "" {
		epStr = cfg.EndpointV6
	}
	ip := net.ParseIP(epStr)
	if ip == nil {
		return nil, fmt.Errorf("invalid QUIC endpoint IP %q", epStr)
	}
	return &net.UDPAddr{IP: ip, Port: internal.WARPMasquePort}, nil
}

func closeResult(r *api.ConnectResult) {
	if r == nil {
		return
	}
	if r.H3TR != nil {
		_ = r.H3TR.Close()
	}
	if r.UDPConn != nil {
		_ = r.UDPConn.Close()
	}
}

func sleepCtx(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		return ctx.Err()
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

func backoff(current, initial, max time.Duration) time.Duration {
	next := current * 2
	if next > max {
		return max
	}
	if next < initial {
		return initial
	}
	return next
}

type bufPool struct {
	cap  int
	pool sync.Pool
}

func newBufPool(capacity int) *bufPool {
	p := &bufPool{cap: capacity}
	p.pool.New = func() any {
		b := make([]byte, capacity)
		return &b
	}
	return p
}

func (p *bufPool) get() []byte { return *(p.pool.Get().(*[]byte)) }
func (p *bufPool) put(b []byte) {
	if cap(b) == p.cap {
		p.pool.Put(&b)
	}
}
