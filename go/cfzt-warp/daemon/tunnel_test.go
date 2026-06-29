package daemon

import (
	"context"
	"errors"
	"testing"
	"time"
)

// mockDevice satisfies TunnelDevice for unit testing.
type mockDevice struct {
	readCh  chan []byte
	written [][]byte
	closed  bool
	readErr error
}

func newMockDevice() *mockDevice {
	return &mockDevice{readCh: make(chan []byte, 16)}
}

func (m *mockDevice) Read(buf []byte) (int, error) {
	if m.readErr != nil {
		return 0, m.readErr
	}
	pkt, ok := <-m.readCh
	if !ok {
		return 0, errors.New("device closed")
	}
	n := copy(buf, pkt)
	return n, nil
}

func (m *mockDevice) Write(buf []byte) error {
	cp := make([]byte, len(buf))
	copy(cp, buf)
	m.written = append(m.written, cp)
	return nil
}

func TestBufPool_GetPut(t *testing.T) {
	p := newBufPool(1500)

	buf := p.get()
	if len(buf) != 1500 {
		t.Errorf("buf len = %d, want 1500", len(buf))
	}
	p.put(buf)

	// Get again — should reuse (no way to assert identity in pure Go, but must not panic)
	buf2 := p.get()
	if len(buf2) != 1500 {
		t.Errorf("buf2 len = %d, want 1500", len(buf2))
	}
}

func TestBufPool_WrongCapacityNotPooled(t *testing.T) {
	p := newBufPool(1500)
	wrongBuf := make([]byte, 100) // wrong capacity
	p.put(wrongBuf)               // should be silently discarded, not panic
	buf := p.get()
	if len(buf) != 1500 {
		t.Errorf("buf len = %d, want 1500", len(buf))
	}
}

func TestSleepCtx_Cancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	err := sleepCtx(ctx, 10*time.Second)
	if !errors.Is(err, context.Canceled) {
		t.Errorf("sleepCtx = %v, want context.Canceled", err)
	}
}

func TestSleepCtx_Completes(t *testing.T) {
	ctx := context.Background()
	start := time.Now()
	err := sleepCtx(ctx, 10*time.Millisecond)
	elapsed := time.Since(start)
	if err != nil {
		t.Errorf("sleepCtx = %v, want nil", err)
	}
	if elapsed < 5*time.Millisecond {
		t.Errorf("sleepCtx returned too fast: %v", elapsed)
	}
}

func TestSleepCtx_ZeroDuration(t *testing.T) {
	ctx := context.Background()
	err := sleepCtx(ctx, 0)
	if err != nil {
		t.Errorf("sleepCtx(0) = %v, want nil", err)
	}
}

func TestBackoff(t *testing.T) {
	initial := 5 * time.Second
	max := 60 * time.Second

	cases := []struct {
		current time.Duration
		want    time.Duration
	}{
		{5 * time.Second, 10 * time.Second},
		{10 * time.Second, 20 * time.Second},
		{30 * time.Second, 60 * time.Second},
		{60 * time.Second, 60 * time.Second}, // capped at max
		{120 * time.Second, 60 * time.Second},
		{1 * time.Second, 5 * time.Second}, // below initial → clamp to initial
	}

	for _, tc := range cases {
		got := backoff(tc.current, initial, max)
		if got != tc.want {
			t.Errorf("backoff(%v) = %v, want %v", tc.current, got, tc.want)
		}
	}
}

func TestMaintainConfig_SelectEndpoint_H2(t *testing.T) {
	cfg := &MaintainConfig{UseH2: true}
	ep, err := cfg.selectEndpoint()
	if err != nil {
		t.Fatalf("selectEndpoint H2: %v", err)
	}
	if ep.Network() != "tcp" {
		t.Errorf("H2 endpoint network = %q, want tcp", ep.Network())
	}
}

func TestMaintainConfig_SelectEndpoint_QUIC_IPv4(t *testing.T) {
	cfg := &MaintainConfig{
		UseH2:      false,
		UseIPv6:    false,
		EndpointV4: "162.159.198.1",
	}
	ep, err := cfg.selectEndpoint()
	if err != nil {
		t.Fatalf("selectEndpoint QUIC IPv4: %v", err)
	}
	if ep.Network() != "udp" {
		t.Errorf("QUIC endpoint network = %q, want udp", ep.Network())
	}
}

func TestMaintainConfig_SelectEndpoint_QUIC_IPv6(t *testing.T) {
	cfg := &MaintainConfig{
		UseH2:      false,
		UseIPv6:    true,
		EndpointV6: "2606:4700:103::1",
	}
	ep, err := cfg.selectEndpoint()
	if err != nil {
		t.Fatalf("selectEndpoint QUIC IPv6: %v", err)
	}
	if ep.Network() != "udp" {
		t.Errorf("QUIC endpoint network = %q, want udp", ep.Network())
	}
}

func TestMaintainConfig_SelectEndpoint_InvalidIP(t *testing.T) {
	cfg := &MaintainConfig{UseH2: false, EndpointV4: "not-an-ip"}
	_, err := cfg.selectEndpoint()
	if err == nil {
		t.Error("expected error for invalid IP")
	}
}

// MaintainTunnel cancellation can only be tested end-to-end against a live
// MASQUE server (ConnectMASQUE is not injectable). The helper tests above
// cover backoff, endpoint selection, and sleepCtx — the pieces that compose
// the reconnect loop. Integration coverage lives in tests/integration/.
