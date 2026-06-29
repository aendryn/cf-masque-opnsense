# Changelog

All notable changes to the Cloudflare Zero Trust OPNsense plugin will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

#### Core Infrastructure
- OPNsense MVC plugin skeleton: Makefile, pkg-descr, plugins.inc.d hook
- CloudflareZT.xml model with organizations, connections, split_tunnel_rules, dns, monitoring sections
- Full configd action set (20 actions): start/stop/restart/status/allstatus, startconn/stopconn/connstatus, register/enroll/rotatekey/rotatekeyscheck, setsecret/delsecret, validatetoken, diagnostics/ping/logs/stats, applydns/removedns
- AES-256-GCM secret store (cfzt_secrets.py) with HKDF-SHA256 key derivation from /etc/hostid; secrets stored at /usr/local/etc/cloudflarezt/secrets.json mode 0600, never in config.xml

#### Protocol Implementation
- cfzt-warp Go daemon (FreeBSD amd64): MASQUE/Connect-IP tunnel via connect-ip-go v0.0.0-20260613064811-66cba32d7d33 and quic-go v0.60.0
- FreeBSD TUN device management via songgao/water with ifconfig address assignment and MTU configuration
- WireGuard mode support using FreeBSD kernel WireGuard interface (wg0-style)
- HTTP/2 fallback path for MASQUE (endpoint 162.159.198.2:443)
- Exponential backoff reconnect loop (initial 5s, max 60s)
- cloudflared tunnel support with YAML config generation and daemon lifecycle management

#### Registration & Key Management
- WARP device registration API client (cfzt_api.py): POST /reg with WireGuard key, PATCH /reg/{id} with ECDSA P-256 MASQUE key
- Automatic MASQUE key enrollment immediately after WireGuard registration
- ECDSA P-256 self-signed TLS client certificate generation for MASQUE mutual TLS
- Public key pinning support in TLS config (VerifyPeerCertificate callback)
- Automatic key rotation with configurable interval (default 30 days), daily cron check at 3am
- cmd_rotatekeyscheck: auto-rotates all connections past threshold

#### Traffic Management
- Split tunnel rules model (exclude/include, CIDR/domain types)
- Full tunnel mode: adds Cloudflare endpoint host routes before setting default route through TUN
- Firewall alias registration for peer IPs via cloudflarezt_firewall() hook
- ApplySplitTunnelRules in tun_freebsd.go for per-connection route tables

#### DNS Integration
- dns.py: Unbound forward-zone config generation for gateway DNS (162.159.36.1) or custom servers
- Atomic config write with unbound-control reload
- configd actions: applydns, removedns

#### Health Monitoring
- cfzt_monitor.py daemon: polls connection status every 30s, auto-restarts failed connections
- OPNsense notification integration (send.py) for connection up/down transitions
- PID file management with clean SIGTERM handling
- configd actions: startmonitor, stopmonitor, monitorstatus

#### OPNsense Hooks
- cloudflarezt_configure(): registers for bootup/newwanip/vpn events — restarts connections on WAN IP change or reboot
- cloudflarezt_firmware_upgrade(): stops all connections cleanly before OPNsense upgrades
- cloudflarezt_xmlrpc_sync(): HA config sync support
- cloudflarezt_syslog(): registers cfzt-warp and cfzt-monitor log facilities

#### Device Management API
- cfzt_api.py: service token enrollment (auth_client_id/auth_client_secret) for headless/MDM deployment
- install_id set to UUID per WARP API requirement; os_version reports FreeBSD
- Additional management endpoints: delete_tunnel, rotate_tunnel_secret, list_tunnel_connections, list_registrations, delete_registration, list_physical_devices, revoke_device

### Fixed
- MASQUE endpoint port corrected to UDP 443 (was incorrectly 2408, which is WireGuard's port)
- Zero Trust SNI updated to zt-masque.cloudflareclient.com (was consumer SNI)
- datetime.utcnow() replaced with datetime.now(timezone.utc) throughout (Python 3.14 deprecation)
- ElementTree truth-value DeprecationWarning fixed in cfzt_config.py
- cfzt-warp TLSConfig now returns error on empty certificate (was silently accepting)

#### GUI
- 8 Volt views: connections, organizations, splittunnel, wizard, diagnostics, logs, dashboard, status
- Status view with per-connection live status table, start/stop buttons, auto-refresh
- Setup wizard combining organization + connection creation in one request
- Dashboard widget showing overall connection health

#### API Controllers
- ServiceController: start/stop/restart/status/allstatus/startconn/stopconn
- ConnectionController: CRUD + register/enroll actions
- OrganizationController: CRUD with API token interception (token never stored in config.xml)
- WizardController: single-request org+connection+register flow

#### Testing
- Python unit tests: 13 passing (cfzt_secrets.py, cfzt_keys.py)
- Python integration tests: 35 passing (config XML parsing, service lifecycle, warp registration flows)
- Go unit tests: 19 passing (TLSConfig, pubkey pinning, backoff, buffer pool, endpoint selection)

### Security
- API tokens and private keys stored encrypted, never in config.xml
- All configd scripts use shell=False (no command injection surface)
- UUID validation in PHP controllers before passing to configd
- User input sanitized via sanitize() in WizardController
- TLS client certificate mutual authentication for MASQUE connections
- Secrets file mode 0600, directory mode 0700
