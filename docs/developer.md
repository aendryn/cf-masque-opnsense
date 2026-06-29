# Developer Guide

## Repository Layout

```
cf-masque-opnsense/
├── go/cfzt-warp/          # Go daemon (MASQUE/WireGuard tunnel process)
│   ├── api/               # TLS config and MASQUE Connect-IP dialer
│   ├── daemon/            # Reconnect loop, packet pumps, backoff
│   ├── internal/          # Shared constants (endpoints, SNI, ports)
│   ├── models/            # JSON config struct read at startup
│   ├── tun/               # FreeBSD TUN device (build-tagged)
│   └── main.go            # Entry point; dispatches to runMASQUE/runWireGuard
├── net/cloudflare-zt/     # OPNsense plugin package
│   └── src/
│       ├── etc/inc/plugins.inc.d/   # Hook registration (services, devices, firewall, WAN)
│       ├── etc/rc.conf.d/           # Service enable/disable template
│       └── opnsense/
│           ├── mvc/app/
│           │   ├── controllers/OPNsense/CloudflareZT/  # PHP API + index controllers
│           │   ├── models/OPNsense/CloudflareZT/       # XML schema + ACL + Menu
│           │   └── views/OPNsense/CloudflareZT/        # Volt templates
│           ├── scripts/CloudflareZT/   # Python configd scripts
│           └── service/conf/actions.d/ # configd action definitions
├── tests/
│   ├── unit/python/        # pytest unit tests (cfzt_secrets, cfzt_keys)
│   └── integration/        # pytest integration tests (config, service, warp)
└── docs/                   # This documentation
```

## Building the Go Daemon

```sh
cd go/cfzt-warp
go build -o cfzt-warp .          # build for host (dev/test)

# Cross-compile for FreeBSD amd64 (production target)
GOOS=freebsd GOARCH=amd64 go build -o cfzt-warp .
```

The Makefile in `net/cloudflare-zt/` cross-compiles and installs to `/usr/local/sbin/cfzt-warp` during `make install`.

## Running Tests

```sh
# Go tests
cd go/cfzt-warp
go test ./...

# Python tests (requires cryptography package)
pip install pytest cryptography
pytest tests/

# PHP unit tests (requires PHP + Composer)
composer install
phpunit
```

The PHP tests stub all OPNsense/Phalcon framework classes and run without a
full OPNsense install. They cover: UUID validation (injection prevention),
POST-only guards, and api_token interception in OrganizationController.

## Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| `connect-ip-go` | v0.0.0-20260613064811 | Cloudflare's Connect-IP fork (non-RFC) |
| `quic-go` | v0.60.0 | QUIC transport for MASQUE |
| `songgao/water` | v0.0.0-20200317... | FreeBSD TUN device |
| `yosida95/uritemplate` | v3.0.2 | URI template for MASQUE path |

## Protocol Details

### MASQUE Connection Sequence

1. Load ECDSA P-256 private key (DER, base64) from secrets store
2. Load self-signed TLS certificate (DER, base64) from secrets store
3. Call `api.TLSConfig()` — builds `tls.Config` with client cert + optional pubkey pinning
4. Call `api.ConnectMASQUE()`:
   - QUIC: `quic.Dial` → `http3.Transport` → `connectip.Dial` with `cf-connect-ip` protocol
   - H2 fallback: `http2.Transport` → `connectip.DialH2`
5. Two goroutines pump packets: TUN→MASQUE and MASQUE→TUN
6. On error: exponential backoff (5s → 10s → 20s → ... → 60s max), then reconnect

### Secret Storage

All sensitive values use a two-level reference system:
- `config.xml` stores a **reference key** (e.g., `masque_privkey_<uuid>`)
- `cfzt_secrets.py` stores the **value** encrypted in `/usr/local/etc/cloudflarezt/secrets.json`
- Encryption: AES-256-GCM with key = HKDF-SHA256(SHA256(`/etc/hostid`), salt="cloudflarezt")
- File permissions: 0600 (root only)

Never add code that writes secret values to `config.xml` or logs.

### Adding a New Protocol

1. Add a new option to `CloudflareZT.xml` `<protocol>` field
2. Add a handler branch in `service.py` `start_connection()`
3. Add a `run<Protocol>` function in `main.go` if it uses the Go daemon
4. Add a build-tagged file in `tun/` if it needs a new interface type
5. Update `cloudflarezt_devices()` in `plugins.inc.d` if the interface pattern changes

### Adding a New configd Action

1. Add a `[name]` section to `actions_cloudflarezt.conf`
2. Add the corresponding `cmd_<name>()` function to the appropriate Python script
3. Wire it up from a PHP controller via `$backend->configdRun('cloudflarezt name ...')`
4. Add a test in `tests/integration/`

## Code Conventions

- **Python scripts**: no direct `config.xml` reads (use `cfzt_config.get_config()`); no `shell=True`; all subprocess calls use lists
- **Go**: build tags `//go:build freebsd` for platform-specific code, `//go:build !freebsd` for stubs
- **PHP**: validate UUID format before passing to configd; use `sanitize()` for user inputs; never store secrets in model fields
- **Tests**: patch `service.*` names (not `cfzt_secrets.*`) when mocking imported functions

## Security Model

- Secrets encrypted at rest; key is host-bound (derived from `/etc/hostid`)
- No `shell=True` in any configd script — prevents command injection via UUID parameters
- PHP controllers validate UUID format with regex before passing to configd
- API tokens intercepted in `OrganizationController::setAction()` before model save
- TLS pubkey pinning available for MASQUE endpoint verification
