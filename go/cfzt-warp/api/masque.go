package api

import (
	"context"
	"crypto/ecdsa"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"fmt"
	"net"
	"net/http"

	connectip "github.com/Diniboy1123/connect-ip-go"
	"github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/http3"
	"github.com/yosida95/uritemplate/v3"
	"golang.org/x/net/http2"

	"github.com/opnsense/cloudflare-zt/cfzt-warp/internal"
)

// TLSConfig builds a TLS configuration for MASQUE connections.
// Uses mutual TLS with the device's ECDSA certificate.
// Pins the endpoint's public key when endpointPubkeyPEM is provided.
func TLSConfig(privKeyDERb64, certDERb64, endpointPubkeyPEM, sni string) (*tls.Config, error) {
	privDER, err := base64.StdEncoding.DecodeString(privKeyDERb64)
	if err != nil {
		return nil, fmt.Errorf("decode private key: %w", err)
	}
	privKey, err := x509.ParseECPrivateKey(privDER)
	if err != nil {
		return nil, fmt.Errorf("parse private key: %w", err)
	}

	if certDERb64 == "" {
		return nil, errors.New("certificate is required")
	}
	certDER, err := base64.StdEncoding.DecodeString(certDERb64)
	if err != nil {
		return nil, fmt.Errorf("decode certificate: %w", err)
	}

	tlsCert := tls.Certificate{
		Certificate: [][]byte{certDER},
		PrivateKey:  privKey,
	}

	cfg := &tls.Config{
		Certificates:       []tls.Certificate{tlsCert},
		ServerName:         sni,
		NextProtos:         []string{http3.NextProtoH3},
		InsecureSkipVerify: true, // SNI doesn't match endpoint IP; we pin pubkey below
	}

	if endpointPubkeyPEM != "" {
		peerPubKey, err := parseECPublicKeyPEM(endpointPubkeyPEM)
		if err != nil {
			return nil, fmt.Errorf("parse endpoint pubkey: %w", err)
		}
		cfg.VerifyPeerCertificate = func(rawCerts [][]byte, _ [][]*x509.Certificate) error {
			if len(rawCerts) == 0 {
				return errors.New("no peer certificate")
			}
			cert, err := x509.ParseCertificate(rawCerts[0])
			if err != nil {
				return err
			}
			ecPub, ok := cert.PublicKey.(*ecdsa.PublicKey)
			if !ok {
				return errors.New("peer certificate does not use ECDSA")
			}
			if !ecPub.Equal(peerPubKey) {
				return errors.New("peer certificate public key does not match pinned key")
			}
			return nil
		}
	}

	return cfg, nil
}

func parseECPublicKeyPEM(pemStr string) (*ecdsa.PublicKey, error) {
	block, _ := pem.Decode([]byte(pemStr))
	if block == nil {
		return nil, errors.New("failed to decode PEM block")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}
	ecPub, ok := pub.(*ecdsa.PublicKey)
	if !ok {
		return nil, errors.New("not an ECDSA public key")
	}
	return ecPub, nil
}

// ConnectResult holds everything needed to pump packets through the tunnel.
type ConnectResult struct {
	IPConn  *connectip.Conn
	UDPConn *net.UDPConn    // non-nil for QUIC/HTTP3
	H3TR    *http3.Transport // non-nil for QUIC/HTTP3; caller must Close
}

// ConnectMASQUE establishes a Connect-IP tunnel over QUIC/HTTP3 (primary) or
// HTTP/2 (fallback). Returns a ConnectResult ready for packet forwarding.
func ConnectMASQUE(ctx context.Context, tlsCfg *tls.Config, endpoint net.Addr, useH2 bool) (*ConnectResult, *http.Response, error) {
	tmpl := uritemplate.MustNew(internal.ConnectURI)
	extra := http.Header{"User-Agent": []string{""}}

	if useH2 {
		tcpEp, ok := endpoint.(*net.TCPAddr)
		if !ok {
			return nil, nil, errors.New("HTTP/2 mode requires *net.TCPAddr endpoint")
		}
		h2Hdrs := extra.Clone()
		h2Hdrs.Set("cf-connect-proto", "cf-connect-ip")
		h2Hdrs.Set("pq-enabled", "false")

		h2Client, err := newH2Client(tlsCfg, tcpEp)
		if err != nil {
			return nil, nil, fmt.Errorf("build HTTP/2 client: %w", err)
		}
		ipConn, rsp, err := connectip.DialH2(ctx, h2Client, tmpl, h2Hdrs)
		if err != nil {
			return nil, nil, fmt.Errorf("connect-ip dial H2: %w", err)
		}
		return &ConnectResult{IPConn: ipConn}, rsp, nil
	}

	udpEp, ok := endpoint.(*net.UDPAddr)
	if !ok {
		return nil, nil, errors.New("QUIC mode requires *net.UDPAddr endpoint")
	}

	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		res, rsp, err := connectH3(ctx, tlsCfg, tmpl, extra, udpEp)
		if err == nil {
			return res, rsp, nil
		}
		lastErr = err
	}
	return nil, nil, fmt.Errorf("connect-ip dial QUIC: %w", lastErr)
}

func connectH3(ctx context.Context, tlsCfg *tls.Config, tmpl *uritemplate.Template,
	extra http.Header, endpoint *net.UDPAddr) (*ConnectResult, *http.Response, error) {

	var udpConn *net.UDPConn
	var err error
	if endpoint.IP.To4() == nil {
		udpConn, err = net.ListenUDP("udp6", &net.UDPAddr{IP: net.IPv6zero, Port: 0})
	} else {
		udpConn, err = net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4zero, Port: 0})
	}
	if err != nil {
		return nil, nil, fmt.Errorf("listen UDP: %w", err)
	}

	quicCfg := &quic.Config{
		EnableDatagrams:   true,
		MaxIdleTimeout:    0, // managed by keepalive
		KeepAlivePeriod:   25_000_000_000, // 25s
	}
	conn, err := quic.Dial(ctx, udpConn, endpoint, tlsCfg, quicCfg)
	if err != nil {
		_ = udpConn.Close()
		return nil, nil, fmt.Errorf("QUIC dial: %w", err)
	}

	tr := &http3.Transport{
		EnableDatagrams: true,
		AdditionalSettings: map[uint64]uint64{
			// SETTINGS_H3_DATAGRAM_00 (deprecated but still sent by official client)
			0x276: 1,
		},
		DisableCompression: true,
	}
	hconn := tr.NewClientConn(conn)

	ipConn, rsp, err := connectip.Dial(ctx, hconn, tmpl, "cf-connect-ip", extra, true)
	if err != nil {
		_ = tr.Close()
		_ = conn.CloseWithError(0, "connect-ip dial failed")
		_ = udpConn.Close()
		return nil, nil, err
	}

	return &ConnectResult{IPConn: ipConn, UDPConn: udpConn, H3TR: tr}, rsp, nil
}

func newH2Client(tlsCfg *tls.Config, endpoint *net.TCPAddr) (*http.Client, error) {
	h2TLS := tlsCfg.Clone()
	h2TLS.NextProtos = []string{"h2"}

	tr := &http2.Transport{
		DialTLSContext: func(ctx context.Context, network, _ string, _ *tls.Config) (net.Conn, error) {
			conn, err := (&net.Dialer{}).DialContext(ctx, network, endpoint.String())
			if err != nil {
				return nil, err
			}
			tlsConn := tls.Client(conn, h2TLS)
			if err := tlsConn.HandshakeContext(ctx); err != nil {
				_ = conn.Close()
				return nil, err
			}
			return tlsConn, nil
		},
	}
	return &http.Client{Transport: tr}, nil
}
