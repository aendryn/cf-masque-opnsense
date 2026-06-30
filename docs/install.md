# Installation Guide

## Prerequisites

- OPNsense 24.1 or later (FreeBSD 14+)
- Cloudflare Zero Trust account

No additional packages are required. The plugin ships as a self-contained package:
- `cfzt-warp` (MASQUE/WireGuard tunnel daemon) — bundled at `/usr/local/sbin/cfzt-warp`
- `cloudflared` (Cloudflare Tunnel connector) — bundled at `/usr/local/bin/cloudflared`
- `wireguard-tools` — listed as a package dependency, installed automatically

## Install the Plugin

The plugin is distributed via a self-hosted FreeBSD pkg repository. Two steps:

```sh
# Step 1 — add the repository (once per router)
pkg add https://github.com/aendryn/cf-masque-opnsense/releases/latest/download/os-repo-aendryn-1.0.0.pkg

# Step 2 — install the plugin
pkg install os-cloudflare-zt
```

Or via the OPNsense GUI: **System → Firmware → Plugins**, search for `os-cloudflare-zt`, click Install (the repository must be added first as above).

## First-Time Setup

### Option A: Setup Wizard (recommended)

1. Navigate to **VPN → Cloudflare ZT → Setup Wizard**
2. Enter your Cloudflare organization name and API token (needs "Zero Trust Write" scope)
3. Choose a protocol (WARP MASQUE recommended)
4. Click **Register Device** — the plugin enrolls a device with Cloudflare and stores keys securely

### Option B: Manual setup

**Step 1 — Add organization**

Go to **VPN → Cloudflare ZT → Organizations**, click +.

- **Name**: any label (e.g. "Acme Corp")
- **Team name**: your Cloudflare team name (from `<team>.cloudflareaccess.com`)
- **Account ID**: found in Cloudflare dashboard sidebar
- **API Token**: create at `cloudflare.com/profile/api-tokens` with "Zero Trust Write" scope

**Step 2 — Add connection**

Go to **VPN → Cloudflare ZT → Connections**, click +.

- **Protocol**: WARP MASQUE (recommended), WARP WireGuard, or Cloudflare Tunnel
- **Organization**: select the org from Step 1
- **MTU**: 1280 (safe default; raise to 1460 only if needed)

**Step 3 — Register device**

Select the connection, click **Register**. The plugin:
1. Generates a WireGuard key and registers with `api.cloudflareclient.com`
2. Generates an ECDSA P-256 key and enrolls it for MASQUE
3. Stores all secrets encrypted on disk (never in config.xml)

**Step 4 — Enable and start**

Enable the plugin at **VPN → Cloudflare ZT → Dashboard** and click Apply. The connection starts automatically.

## Zero Trust Enrollment (headless, no browser)

For router/headless devices, use a Cloudflare service token instead of interactive login:

1. Create a service token at **Cloudflare Zero Trust → Access → Service Auth**
2. Create an enrollment rule with **Service Auth** action (not "Allow") referencing the token
3. In the connection settings, enter the **Client ID** and **Client Secret** from the service token
4. Click **Register** — no browser visit required

## Firewall Considerations

Allow outbound from the router:

| Destination | Port | Protocol | Purpose |
|---|---|---|---|
| `162.159.198.1/32` | 443 | UDP | MASQUE QUIC primary |
| `162.159.198.2/32` | 443 | TCP | MASQUE HTTP/2 fallback |
| `162.159.193.0/24` | 2408 | UDP | WireGuard tunnel |
| `162.159.137.105`, `162.159.138.105` | 443 | TCP | Device orchestration API |
| `162.159.36.1/32` | 443 | TCP | Gateway DoH |

## Verifying the Installation

```sh
# Check service status
configctl cloudflarezt status

# Ping Cloudflare endpoints
configctl cloudflarezt ping

# View connection details
configctl cloudflarezt allstatus
```

Or via the GUI: **VPN → Cloudflare ZT → Dashboard**.
