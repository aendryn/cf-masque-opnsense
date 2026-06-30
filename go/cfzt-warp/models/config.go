package models

// DaemonConfig is the JSON config written by service.py and read by cfzt-warp at startup.
type DaemonConfig struct {
	ConnectionUUID string `json:"connection_uuid"`
	Protocol       string `json:"protocol"` // warp_masque | warp_wireguard

	DeviceID   string `json:"device_id"`
	ClientIPv4 string `json:"client_ipv4"`
	ClientIPv6 string `json:"client_ipv6"`

	// MASQUE fields
	EndpointV4      string `json:"endpoint_v4"`
	EndpointV6      string `json:"endpoint_v6"`
	EndpointPubkey  string `json:"endpoint_pubkey"`  // PEM ECDSA public key for pinning
	MasquePrivateKey string `json:"masque_private_key"` // base64 DER ECDSA P-256 private key
	MasqueCertDER   string `json:"masque_cert_der"`   // base64 DER self-signed TLS cert

	// WireGuard fields
	WgPrivateKey string `json:"wg_private_key"`
	WgPeerPubkey string `json:"wg_peer_pubkey"`
	WgPeerPort   int    `json:"wg_peer_port"`

	// Network settings
	MTU            int    `json:"mtu"`
	UseIPv6        bool   `json:"use_ipv6"`
	PreferIPv6     bool   `json:"prefer_ipv6"`
	TunnelMode     string `json:"tunnel_mode"` // split | full
	DNSMode        string `json:"dns_mode"`    // system | cloudflare_gateway | custom
	BindInterface  string `json:"bind_interface"`

	// Reliability
	ReconnectDelay  int  `json:"reconnect_delay"`
	AlwaysReconnect bool `json:"always_reconnect"`
	HTTP2Fallback   bool `json:"http2_fallback"`

	// Daemon management
	PIDFile   string `json:"pid_file"`
	LogIdent  string `json:"log_ident"`
}
