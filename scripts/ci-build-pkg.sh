#!/bin/sh
# Runs inside vmactions/freebsd-vm.
# Builds os-cloudflare-zt.pkg, os-repo-aendryn.pkg, and a signed pkg repo.
# Usage: ci-build-pkg.sh <version> [existing-pkgs-dir]
set -e

VERSION="${1:-1.0.0}"
EXISTING_PKGS="${2:-}"
ARCH="freebsd:14:amd64"
DIST="dist"
REPO="$DIST/repo/$ARCH/latest"

mkdir -p "$DIST" "$REPO/All"

# ── os-cloudflare-zt ─────────────────────────────────────────────────────
build_main() {
    stage=$(mktemp -d)
    meta=$(mktemp -d)   # metadata dir: +MANIFEST + deinstall scripts
    plist=$(mktemp)

    # Map src/ to install paths:
    #   src/usr/... → /usr/...
    #   src/...     → /usr/local/...  (OPNsense prefix convention)
    find net/cloudflare-zt/src -type f ! -name '.gitkeep' | while read -r src; do
        rel="${src#net/cloudflare-zt/src/}"
        case "$rel" in
            usr/*) dst="$stage/$rel" ;;
            *)     dst="$stage/usr/local/$rel" ;;
        esac
        mkdir -p "$(dirname "$dst")" && install -m 0644 "$src" "$dst"
    done
    chmod 0755 "$stage/usr/local/sbin/cfzt-warp" \
               "$stage/usr/local/bin/cloudflared"
    find "$stage/usr/local/opnsense/scripts" -name '*.py' -exec chmod 0755 {} \;

    find "$stage" -type f | sed "s|$stage/||" | sort > "$plist"
    flatsize=$(find "$stage" -type f | xargs stat -f '%z' | awk '{sum+=$1} END{print sum+0}')

    # Manifest goes in the metadata dir (used with -m, not -M)
    cat > "$meta/+MANIFEST" <<EOF
name: "os-cloudflare-zt"
version: "${VERSION}"
origin: "net/os-cloudflare-zt"
comment: "Cloudflare Zero Trust VPN plugin for OPNsense"
desc: "Integrates Cloudflare Zero Trust as a native OPNsense VPN. Supports WARP via MASQUE/QUIC and WireGuard, Cloudflare Tunnel, split and full tunnel modes, automatic key rotation, and health monitoring."
arch: "${ARCH}"
www: "https://github.com/aendryn/cf-masque-opnsense"
maintainer: "aendryn@github"
prefix: "/"
flatsize: ${flatsize}
deps: {
    wireguard-tools: {origin: "net/wireguard-tools"}
    py311-cryptography: {origin: "security/py-cryptography"}
}
EOF

    # Deinstall scripts alongside the manifest in the metadata dir
    cat > "$meta/+PRE_DEINSTALL" <<'SH'
#!/bin/sh
/usr/local/sbin/configctl cloudflarezt stop 2>/dev/null || true
/usr/local/sbin/configctl cloudflarezt stopmonitor 2>/dev/null || true
/usr/local/sbin/configctl cloudflarezt removedns 2>/dev/null || true
for iface in $(ifconfig -l | tr ' ' '\n' | grep '^cfzt'); do
    ifconfig "$iface" destroy 2>/dev/null || true
done
rm -f /var/run/cfzt-*.pid /var/run/cfzt-monitor.pid /var/run/cfzt-iface-*
SH

    cat > "$meta/+POST_DEINSTALL" <<'SH'
#!/bin/sh
/usr/sbin/unbound-control reload 2>/dev/null || true
SH

    pkg create -m "$meta" -r "$stage" -p "$plist" -o "$DIST/"
    rm -rf "$stage" "$meta" "$plist"
    echo "==> Built: $DIST/os-cloudflare-zt-${VERSION}.pkg"
}

# ── os-repo-aendryn (bootstrap) ──────────────────────────────────────────
build_bootstrap() {
    stage=$(mktemp -d)
    meta=$(mktemp -d)
    plist=$(mktemp)

    mkdir -p "$stage/usr/local/etc/pkg/repos" "$stage/usr/local/share/aendryn"
    install -m 0644 net/repo-bootstrap/src/usr/local/etc/pkg/repos/aendryn.conf \
        "$stage/usr/local/etc/pkg/repos/aendryn.conf"
    install -m 0644 net/repo-bootstrap/src/usr/local/share/aendryn/pubkey.rsa \
        "$stage/usr/local/share/aendryn/pubkey.rsa"

    find "$stage" -type f | sed "s|$stage/||" | sort > "$plist"
    flatsize=$(find "$stage" -type f | xargs stat -f '%z' | awk '{sum+=$1} END{print sum+0}')

    cat > "$meta/+MANIFEST" <<EOF
name: "os-repo-aendryn"
version: "1.0.0"
origin: "net/os-repo-aendryn"
comment: "aendryn OPNsense plugin repository configuration"
desc: "Configures pkg to use the aendryn OPNsense plugin repository so that os-cloudflare-zt and future plugins appear in System -> Firmware -> Plugins."
arch: "freebsd:*:*"
www: "https://github.com/aendryn/cf-masque-opnsense"
maintainer: "aendryn@github"
prefix: "/"
flatsize: ${flatsize}
EOF

    pkg create -m "$meta" -r "$stage" -p "$plist" -o "$DIST/"
    rm -rf "$stage" "$meta" "$plist"
    echo "==> Built: $DIST/os-repo-aendryn-1.0.0.pkg"
}

build_main
build_bootstrap

# Carry over existing packages so packagesite.yaml lists all plugins
if [ -n "$EXISTING_PKGS" ] && [ -d "$EXISTING_PKGS" ]; then
    cp "$EXISTING_PKGS"/*.pkg "$REPO/All/" 2>/dev/null || true
fi

cp "$DIST"/*.pkg "$REPO/All/"
pkg repo "$REPO" "$(pwd)/.ci-signing.key"

echo "==> Repo contents:"
ls -la "$REPO/All/"
ls -la "$REPO/"
