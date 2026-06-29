package internal

// Cloudflare WARP MASQUE connection constants.
// These are derived from reverse engineering of official WARP clients.
const (
	// MASQUE QUIC/HTTP3 primary endpoint — port 443 UDP (NOT 2408; that's WireGuard)
	WARPMasqueEndpointV4 = "162.159.198.1"
	WARPMasqueEndpointV6 = "2606:4700:103::1"
	WARPMasquePort       = 443

	// HTTP/2 CONNECT-IP fallback endpoint (TCP 443)
	WARPH2EndpointV4 = "162.159.198.2"
	WARPH2Port       = 443

	// WireGuard endpoint (separate from MASQUE)
	WARPWireGuardEndpointV4 = "162.159.193.1"
	WARPWireGuardPort       = 2408

	// TLS SNI values — use ZT variant for Zero Trust org deployments
	MasqueSNIConsumer  = "consumer-masque.cloudflareclient.com"
	MasqueSNIZeroTrust = "zt-masque.cloudflareclient.com"

	// MASQUE Connect-IP URI template (Cloudflare non-RFC authority + path)
	ConnectURI = "https://cloudflareaccess.com/v1/masque{?address,port}"

	// State file prefix for interface name (read by monitor.py)
	IfaceStateFilePrefix = "/var/run/cfzt-iface-"

	// DatagramContextIDHeadroom is headroom for QUIC datagram context ID
	DatagramContextIDHeadroom = 1
)
