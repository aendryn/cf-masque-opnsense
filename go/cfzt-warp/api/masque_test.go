package api

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/pem"
	"math/big"
	"testing"
	"time"
)

func generateTestKeypair(t *testing.T) (*ecdsa.PrivateKey, []byte, string) {
	t.Helper()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}

	privDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		t.Fatalf("marshal private key: %v", err)
	}

	// Self-signed cert
	tmpl := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: "test"},
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(24 * time.Hour),
	}
	certDER, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		t.Fatalf("create cert: %v", err)
	}

	return key, privDER, base64.StdEncoding.EncodeToString(certDER)
}

func TestTLSConfig_ValidKeypair(t *testing.T) {
	_, privDER, certDERb64 := generateTestKeypair(t)
	privDERb64 := base64.StdEncoding.EncodeToString(privDER)

	cfg, err := TLSConfig(privDERb64, certDERb64, "", "example.com")
	if err != nil {
		t.Fatalf("TLSConfig: %v", err)
	}

	if cfg.ServerName != "example.com" {
		t.Errorf("ServerName = %q, want %q", cfg.ServerName, "example.com")
	}
	if len(cfg.Certificates) != 1 {
		t.Errorf("len(Certificates) = %d, want 1", len(cfg.Certificates))
	}
}

func TestTLSConfig_InvalidPrivKey(t *testing.T) {
	_, err := TLSConfig("not-base64!!!", "dGVzdA==", "", "example.com")
	if err == nil {
		t.Fatal("expected error for invalid private key base64")
	}
}

func TestTLSConfig_WithPubkeyPinning(t *testing.T) {
	key, privDER, certDERb64 := generateTestKeypair(t)
	privDERb64 := base64.StdEncoding.EncodeToString(privDER)

	// Encode public key as PEM
	pubDER, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	pubPEM := string(pem.EncodeToMemory(&pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: pubDER,
	}))

	cfg, err := TLSConfig(privDERb64, certDERb64, pubPEM, "example.com")
	if err != nil {
		t.Fatalf("TLSConfig with pubkey pinning: %v", err)
	}
	if cfg.VerifyPeerCertificate == nil {
		t.Error("VerifyPeerCertificate should be set when pubkey is provided")
	}
}

func TestTLSConfig_PubkeyPinning_WrongKey(t *testing.T) {
	_, privDER, certDERb64 := generateTestKeypair(t)
	privDERb64 := base64.StdEncoding.EncodeToString(privDER)

	// Generate a different key to pin — mismatch should cause verification failure
	wrongKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	wrongPubDER, _ := x509.MarshalPKIXPublicKey(&wrongKey.PublicKey)
	wrongPubPEM := string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: wrongPubDER}))

	cfg, err := TLSConfig(privDERb64, certDERb64, wrongPubPEM, "example.com")
	if err != nil {
		t.Fatal(err)
	}

	// Build a fake peer cert from the original key (not the pinned one)
	_, origPrivDER, origCertDERb64 := generateTestKeypair(t)
	origCertDER, _ := base64.StdEncoding.DecodeString(origCertDERb64)
	_ = origPrivDER

	verifyErr := cfg.VerifyPeerCertificate([][]byte{origCertDER}, nil)
	if verifyErr == nil {
		t.Error("expected verification error for wrong pubkey, got nil")
	}
}

func TestParseECPublicKeyPEM_Valid(t *testing.T) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	pubDER, _ := x509.MarshalPKIXPublicKey(&key.PublicKey)
	pubPEM := string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: pubDER}))

	parsed, err := parseECPublicKeyPEM(pubPEM)
	if err != nil {
		t.Fatalf("parseECPublicKeyPEM: %v", err)
	}
	if !parsed.Equal(&key.PublicKey) {
		t.Error("parsed key does not match original")
	}
}

func TestParseECPublicKeyPEM_Invalid(t *testing.T) {
	_, err := parseECPublicKeyPEM("not a pem block")
	if err == nil {
		t.Error("expected error for invalid PEM")
	}
}

func TestTLSConfig_NextProto(t *testing.T) {
	_, privDER, certDERb64 := generateTestKeypair(t)
	cfg, err := TLSConfig(base64.StdEncoding.EncodeToString(privDER), certDERb64, "", "x")
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, p := range cfg.NextProtos {
		if p == "h3" {
			found = true
		}
	}
	if !found {
		t.Errorf("NextProtos %v does not include h3", cfg.NextProtos)
	}
}

// TLS must use proper CA verification (InsecureSkipVerify must be false).
func TestTLSConfig_VerifiesServerCert(t *testing.T) {
	_, privDER, certDERb64 := generateTestKeypair(t)
	cfg, err := TLSConfig(base64.StdEncoding.EncodeToString(privDER), certDERb64, "", "zt-masque.cloudflareclient.com")
	if err != nil {
		t.Fatal(err)
	}
	if cfg.InsecureSkipVerify {
		t.Error("InsecureSkipVerify must be false; server cert is verified via system CAs + ServerName")
	}
}

// TLSConfig with empty cert should fail gracefully.
func TestTLSConfig_EmptyCert(t *testing.T) {
	_, privDER, _ := generateTestKeypair(t)
	_, err := TLSConfig(base64.StdEncoding.EncodeToString(privDER), "", "", "x")
	if err == nil {
		t.Error("expected error for empty cert")
	}
}

// Ensure TLSConfig returns a usable *tls.Config (not just non-nil).
func TestTLSConfig_Usable(t *testing.T) {
	_, privDER, certDERb64 := generateTestKeypair(t)
	cfg, err := TLSConfig(base64.StdEncoding.EncodeToString(privDER), certDERb64, "", "example.com")
	if err != nil {
		t.Fatal(err)
	}
	// Should be able to clone without panic
	_ = cfg.Clone()
	var _ *tls.Config = cfg
}
