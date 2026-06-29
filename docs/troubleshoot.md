# Troubleshooting Guide

## Connection Won't Start

**Check registration status:**
```sh
configctl cloudflarezt allstatus
```
If `registration_status` is `unregistered`, run **Register** from the GUI or:
```sh
configctl cloudflarezt register <uuid>
```

**Check the binary exists:**
```sh
ls -la /usr/local/sbin/cfzt-warp
ls -la /usr/local/bin/cloudflared   # for tunnel mode
```

**Check for errors in logs:**
```sh
configctl cloudflarezt logs <uuid> 50
# or directly:
grep cfzt-warp /var/log/system.log | tail -50
```

## Registration Fails

**HTTP 403 from WARP API:**
- Your API token may lack "Zero Trust Write" scope
- The device may be blocked by a Zero Trust policy
- Try with a service token: set `auth_client_id` and `auth_client_secret` in connection settings

**HTTP 429 (rate limit):**
- Wait a few minutes and retry
- The plugin will report this as `HTTP 429` in the result

**TLS error during registration:**
- The WARP API requires TLS 1.2 exactly. Some network filtering may interfere.
- Try: `configctl cloudflarezt ping` to confirm connectivity to `162.159.198.x`

## MASQUE Tunnel Fails to Connect

**No UDP 443 reachability:**
```sh
configctl cloudflarezt ping
```
If `162.159.198.1:443/udp` shows unreachable, your upstream firewall may be blocking UDP 443. The daemon automatically falls back to HTTP/2 (TCP 443) — check `http2_fallback` is enabled in the connection settings.

**TLS handshake failure:**
- The client certificate may have expired (validity: 10 years from enrollment) — unlikely
- The MASQUE key may need re-enrollment: `configctl cloudflarezt rotatekey <uuid>`

**QUIC connection drops immediately:**
- Increase MTU if the network does path MTU discovery poorly. Try lowering to 1200.
- Check `EnableDatagrams` is supported by your network (some UDP middleboxes strip QUIC extensions)

## WireGuard Mode Issues

**Interface not created:**
```sh
ifconfig -a | grep wg
kldstat | grep if_wg    # must show the wg kernel module
```
Load the module: `kldload if_wg` and ensure `if_wg_load="YES"` in `/boot/loader.conf`.

**No traffic through tunnel:**
```sh
wg show   # check peer handshake time
```
If last handshake is never/stale, the peer endpoint may have rotated — re-register the device.

## DNS Not Resolving Through Gateway

**Verify Unbound config was written:**
```sh
cat /var/unbound/conf.d/cloudflarezt.conf
```
If missing: `configctl cloudflarezt applydns`

**Verify Unbound is using it:**
```sh
unbound-control status
dig @127.0.0.1 example.com   # should resolve via Gateway
```

**Unbound reload didn't pick up changes:**
```sh
pluginctl -c dns   # forces full Unbound reconfigure
```

## Health Monitor Not Starting

```sh
configctl cloudflarezt monitorstatus
```
If not running: `configctl cloudflarezt startmonitor`

Check monitor logs: `grep cfzt-monitor /var/log/system.log | tail -20`

The monitor requires `configctl` to be accessible at `/usr/local/sbin/configctl`.

## Secrets Lost After System Restore

Secrets are encrypted with a key derived from `/etc/hostid`. After restoring config.xml to **different hardware**, secrets cannot be decrypted. Fix:

1. Re-register each connection: `configctl cloudflarezt register <uuid>`

After restoring to the **same hardware** (same hostid), secrets decrypt normally. No action needed.

## High CPU / Memory Usage

The cfzt-warp daemon is a single Go binary per connection. Each connection uses ~5–15 MB RSS at idle.

If CPU is high, check for reconnect loops:
```sh
grep 'MASQUE connect failed' /var/log/system.log | tail -20
```
Persistent failures trigger exponential backoff up to 60s. Verify connectivity first.

## Viewing Raw Diagnostics

```sh
configctl cloudflarezt diagnostics <uuid>
```

Output includes: process status, registered IPs, TUN interface addresses, active routes, and connectivity probe results.

## Getting Support

Collect a diagnostics bundle before reporting issues:
```sh
configctl cloudflarezt diagnostics all > /tmp/cfzt-diag.json
configctl cloudflarezt logs all 500 >> /tmp/cfzt-diag.json
```
