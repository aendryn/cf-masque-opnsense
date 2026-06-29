# Administrator Guide

## Architecture Overview

The plugin has three layers:

1. **cfzt-warp** — Go daemon that owns the TUN interface and MASQUE/WireGuard tunnel
2. **Python backend** — configd scripts for registration, secrets, DNS, monitoring
3. **OPNsense MVC** — PHP controllers, XML model, Volt GUI, configd action bridge

Secrets (device tokens, private keys, TLS certificates) are stored AES-256-GCM encrypted in `/usr/local/etc/cloudflarezt/secrets.json`. The encryption key is derived from `/etc/hostid` via HKDF-SHA256 and never leaves the router.

## Connection Protocols

### WARP MASQUE (recommended)
- Tunnel: QUIC (HTTP/3) or HTTP/2 fallback to `162.159.198.x:443`
- Auth: ECDSA P-256 mutual TLS client certificate
- Assigned: CGNAT IP from `100.96.0.0/12`
- FIPS-compliant (AES-256-GCM cipher)

### WARP WireGuard
- Tunnel: WireGuard UDP to `162.159.193.x:2408`
- Key: Curve25519 (standard WireGuard)
- Assigned: `172.16.0.2/32`

### Cloudflare Tunnel (cloudflared)
- Outbound-only connector to Cloudflare edge
- Suitable for exposing internal services, not for routing client traffic

## Split Tunnel vs Full Tunnel

**Split tunnel** (default): only traffic in the include list routes through Cloudflare. LAN traffic and non-ZT traffic use the normal default gateway.

**Full tunnel**: all traffic routes through Cloudflare. The plugin adds host routes for Cloudflare endpoints via the normal gateway first, then sets the TUN as the default route.

Configure at **VPN → Cloudflare Zero Trust → Split Tunnel**.

## Key Rotation

Keys auto-rotate every 30 days (configurable per connection). A daily cron job at 3am checks for keys due for rotation and re-enrolls them without downtime — the new key is enrolled before the old one is removed.

Manual rotation: select a connection → **Rotate Key**, or via CLI:
```sh
configctl cloudflarezt rotatekey <uuid>
```

## Health Monitoring

The `cfzt-monitor` daemon polls connections every 30 seconds (configurable). On failure it:
1. Attempts to restart the connection via configd
2. Sends an OPNsense system notification (if enabled)

Configure at **VPN → Cloudflare Zero Trust → Monitoring**.

## WAN Failover

The plugin hooks into OPNsense's `newwanip` event. When the WAN IP changes (failover, PPPoE reconnect), all connections are restarted automatically so the QUIC socket binds to the new address.

## DNS Integration

When **Override DNS** is enabled, the plugin writes an Unbound `forward-zone` config to `/var/unbound/conf.d/cloudflarezt.conf` and reloads Unbound. DNS queries are forwarded to:
- **Gateway DNS**: Cloudflare Gateway at `162.159.36.1` (applies your Gateway policies)
- **Custom servers**: any resolver you specify

## HA / XMLRPC Sync

The plugin registers with OPNsense's HA sync framework. On a primary/secondary pair, the CloudflareZT configuration syncs automatically. Secrets do **not** sync (they are host-bound to `/etc/hostid`); each HA node must register its own device independently.

## Backup and Restore

`config.xml` backup/restore works normally — it contains all non-secret configuration. After restoring to a new system:

1. Re-register each connection (generates new device + keys for the new hostid)
2. Or copy `/usr/local/etc/cloudflarezt/secrets.json` manually if restoring to identical hardware

## Logging

Logs appear in `/var/log/system.log` under the `cfzt-warp`, `cloudflared`, and `cfzt-monitor` facilities. View via **VPN → Cloudflare Zero Trust → Logs** or:

```sh
configctl cloudflarezt logs all 200
```

## CLI Reference

All operations are available via `configctl` (as root):

```sh
configctl cloudflarezt start              # start all enabled connections
configctl cloudflarezt stop               # stop all connections
configctl cloudflarezt restart            # restart all connections
configctl cloudflarezt status             # overall status
configctl cloudflarezt allstatus          # per-connection JSON status
configctl cloudflarezt startconn <uuid>   # start one connection
configctl cloudflarezt stopconn <uuid>    # stop one connection
configctl cloudflarezt connstatus <uuid>  # one connection status
configctl cloudflarezt register <uuid>    # register/re-register device
configctl cloudflarezt rotatekey <uuid>   # rotate MASQUE key now
configctl cloudflarezt rotatekeyscheck    # check + auto-rotate due keys
configctl cloudflarezt ping               # probe Cloudflare endpoints
configctl cloudflarezt diagnostics <uuid> # full diagnostics
configctl cloudflarezt logs <uuid> <n>    # last n log lines
configctl cloudflarezt applydns           # write + apply DNS config
configctl cloudflarezt startmonitor       # start health monitor daemon
configctl cloudflarezt stopmonitor        # stop health monitor daemon
configctl cloudflarezt monitorstatus      # monitor daemon status
```
