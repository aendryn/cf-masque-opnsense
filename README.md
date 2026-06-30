# cf-masque-opnsense

> **Experimental.** This project is provided as-is with no guarantees of stability, correctness, or fitness for any purpose. Use in production environments is at your own risk. The developer accepts no liability for data loss, network outages, or security issues arising from its use.
>
> This project is not affiliated with, endorsed by, or supported by Cloudflare, Inc. Cloudflare, WARP, and Cloudflare Tunnel are trademarks of Cloudflare, Inc.

Cloudflare Zero Trust VPN plugin for OPNsense. Connects your router to Cloudflare's network using WARP (MASQUE/QUIC or WireGuard) or Cloudflare Tunnel, with full OPNsense GUI integration.

## Features

- **WARP via MASQUE/HTTP3** — the same QUIC-based protocol used by the WARP client; falls back to HTTP/2 automatically
- **WARP via WireGuard** — direct WireGuard tunnel to Cloudflare's endpoint
- **Cloudflare Tunnel** (`cloudflared`) — outbound-only tunnel for exposing internal services
- **Split tunnel and full tunnel modes** — per-connection, with a split-tunnel rule editor in the GUI
- **DNS control** — use OPNsense's own Unbound, Cloudflare Gateway, or custom servers; full-tunnel mode automatically adds host routes for Unbound's upstream so DNS never silently breaks
- **Key management** — ECDSA P-256 keys, optional automatic rotation on a configurable schedule
- **Health monitoring** — reconnect loop with configurable backoff, OPNsense notification integration on failure/recovery
- **Secrets never touch config.xml** — AES-256-GCM encryption at rest, keyed from `/etc/hostid`

## Requirements

- OPNsense 24.1 or later (FreeBSD 14, amd64)
- Cloudflare account with Zero Trust enabled (free tier works)

Dependencies (`wireguard-tools`, `py311-cryptography`) are installed automatically with the package.

## Installation

### Step 1 — Add the repository

The plugin is distributed via a self-hosted FreeBSD pkg repository. Add it with a single `pkg add`:

```sh
pkg add https://github.com/aendryn/cf-masque-opnsense/releases/latest/download/os-repo-aendryn-1.0.0.pkg
```

This installs the repo configuration and signing key. You only need to do this once.

### Step 2 — Install the plugin

```sh
pkg install os-cloudflare-zt
```

Or from the OPNsense GUI: **System → Firmware → Plugins**, search for `os-cloudflare-zt`, click **+**.

### Keeping up to date

```sh
pkg upgrade os-cloudflare-zt
```

Or via the GUI: **System → Firmware → Updates**.

## First-time setup

1. **VPN → Cloudflare ZT → Setup Wizard** — add your Cloudflare organization (Account ID + API token with Zero Trust write permission), configure a connection, and register the device.

2. The wizard registers a WARP device with Cloudflare, generates ECDSA keys, and stores the credentials encrypted on disk. Click **Apply and Start** when done.

3. Verify connectivity on the **Dashboard** tab or via **Diagnostics**.

For manual setup (multiple connections, advanced options) use the **Organizations** and **Connections** tabs directly.

## GUI pages

| Page | Path | Purpose |
|------|------|---------|
| Dashboard | VPN → Cloudflare ZT | Status overview for all connections |
| Connections | → Connections | Add/edit/remove WARP or Tunnel connections |
| Organizations | → Organizations | Cloudflare account credentials |
| Split Tunnel | → Split Tunnel | Per-connection include/exclude rules |
| DNS | → DNS | DNS mode: OPNsense / Cloudflare Gateway / Custom |
| Diagnostics | → Diagnostics | Ping, route, and connectivity tests |
| Logs | → Log | Live service log |
| Setup Wizard | → Setup Wizard | Guided first-time configuration |

## DNS

Three modes, configured at **VPN → Cloudflare ZT → DNS**:

| Mode | Behaviour |
|------|-----------|
| **OPNsense DNS** (default) | No override — Unbound resolves as configured in System → General |
| **Cloudflare Gateway** | Forwards all DNS to `162.159.36.1` through your Zero Trust policy |
| **Custom** | Forwards to the servers you specify (comma-separated IPs) |

In **Full Tunnel** mode with **OPNsense DNS**, the daemon automatically adds host routes for each of Unbound's upstream servers via the pre-tunnel gateway so DNS queries bypass the tunnel and reach those servers directly. The routes are removed when the tunnel stops.

Optionally add comma-separated **Search Domains** to mark internal zones as insecure in Unbound (needed for split-DNS with internal hostnames).

## Tunnel modes

**Split tunnel** (default) — only traffic matching the split-tunnel rules goes through the tunnel. Add CIDR or domain rules under **Split Tunnel**.

**Full tunnel** — all traffic is routed through Cloudflare. The original default gateway is saved at startup and restored automatically when the tunnel stops, so the router never loses connectivity.

## Protocols

| Protocol | Use case |
|----------|---------|
| `warp_masque` | Recommended. QUIC/HTTP3 with HTTP/2 fallback. |
| `warp_wireguard` | Use when UDP/QUIC is blocked or for lower overhead. |
| `cloudflared` | Expose internal services via Cloudflare Tunnel (no inbound traffic through WARP). |

## Building from source

Requires Go 1.21+ and an OPNsense/FreeBSD build environment for packaging.

```sh
# Build the Go daemon (cross-compile from any platform)
cd go/cfzt-warp
GOOS=freebsd GOARCH=amd64 CGO_ENABLED=0 go build -o ../../net/cloudflare-zt/src/usr/local/sbin/cfzt-warp .

# cloudflared is built from source in CI — see .github/workflows/release.yml
# and scripts/cloudflared-freebsd-stubs.py for the FreeBSD platform stubs

# Package (run on FreeBSD)
bash scripts/ci-build-pkg.sh 1.0.0
```

Releases are built automatically by GitHub Actions on version tags. The workflow cross-compiles both binaries, packages them with `pkg create`, signs the repo, and publishes to GitHub Pages.

## Security notes

- API tokens and device credentials are stored encrypted (`AES-256-GCM`, key derived via `HKDF-SHA256` from `/etc/hostid`) in `/usr/local/etc/cloudflarezt/secrets.json` (mode `0600`). They are never written to `config.xml` or logged.
- configd scripts do not use shell interpolation for UUID parameters — all external input is validated before use.
- PHP controllers validate UUID format before passing to configd.

## License

BSD 2-Clause. See individual files for copyright headers.
