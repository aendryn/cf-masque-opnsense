//go:build !freebsd

// Stub for non-FreeBSD builds (e.g., development on Linux/macOS).
// Production deployment is FreeBSD only.

package tun

import "errors"

var errNotSupported = errors.New("native TUN only supported on FreeBSD")

type FreeBSDTUN struct{}

func New(_, _ string, _ int) (*FreeBSDTUN, error)                { return nil, errNotSupported }
func (t *FreeBSDTUN) Name() string                               { return "" }
func (t *FreeBSDTUN) MTU() int                                   { return 0 }
func (t *FreeBSDTUN) Read(_ []byte) (int, error)                 { return 0, errNotSupported }
func (t *FreeBSDTUN) Write(_ []byte) error                       { return errNotSupported }
func (t *FreeBSDTUN) Close() error                               { return nil }
func (t *FreeBSDTUN) AddRoute(_ string) error                    { return errNotSupported }
func (t *FreeBSDTUN) DelRoute(_ string) error                    { return errNotSupported }
func (t *FreeBSDTUN) AddDefaultRoute(_ string) error             { return errNotSupported }
func (t *FreeBSDTUN) WriteIfaceStateFile(_ string) error         { return nil }
func (t *FreeBSDTUN) RemoveIfaceStateFile(_ string)              {}
func (t *FreeBSDTUN) ApplySplitTunnelRules(_, _ []string, _ string) error { return errNotSupported }
