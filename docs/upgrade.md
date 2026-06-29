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

## Go Daemon Binary

The cfzt-warp binary is replaced atomically during package upgrade. Running connections are restarted after the upgrade to load the new binary. If a connection is in active use, expect a brief reconnect (handled by the client's reconnect logic on the other end).

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
