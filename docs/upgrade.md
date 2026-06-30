# Upgrade Guide

## General Procedure

1. The firmware hook stops all connections cleanly before OPNsense upgrades
2. After upgrade completes, connections restart automatically via `bootup` hook
3. No manual intervention required for patch-level upgrades

## From Pre-1.0 (Development Builds)

If upgrading from an early development build where secrets were stored differently:

1. Note your device IDs and org settings from the GUI
2. Remove the old secrets file: `rm /usr/local/etc/cloudflarezt/secrets.json`
3. Upgrade the package
4. Re-register each connection: **VPN → Cloudflare Zero Trust → Connections → Register**

## Config Schema Migrations

Schema version is tracked in `CloudflareZT.xml`. When upgrading between minor versions that add new fields, OPNsense's model migration system applies defaults automatically. No manual config editing is required.

## Bundled Binaries

Both `cfzt-warp` and `cloudflared` are shipped inside the package — no separate downloads required. They are replaced atomically during package upgrade. Running connections are restarted after the upgrade to load the new binaries.

To upgrade `cloudflared` to a newer release, update `CLOUDFLARED_VERSION` in `net/cloudflare-zt/Makefile` to the new release tag. The CI pipeline clones cloudflared at that tag, applies the FreeBSD stubs via `scripts/cloudflared-freebsd-stubs.py`, and cross-compiles it. No pre-built FreeBSD binary exists upstream.

## Checking Current Version

```sh
pkg info os-cloudflare-zt
```

## Rollback

OPNsense package rollback:
```sh
pkg install os-cloudflare-zt-<previous-version>
```

Secrets and config are preserved across rollback. No re-registration needed unless the registration API version changed.
