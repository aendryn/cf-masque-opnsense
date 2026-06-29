#!/bin/sh
# Runs inside vmactions/freebsd-vm.
# Builds os-cloudflare-zt.pkg, os-repo-aendryn.pkg, and a signed pkg repo.
# Usage: ci-build-pkg.sh <version>
set -e

VERSION="${1:-1.0.0}"
ARCH="freebsd:14:amd64"
DIST="dist"
REPO="$DIST/repo/$ARCH/latest"

mkdir -p "$DIST" "$REPO/All"

# ── os-cloudflare-zt ─────────────────────────────────────────────────────
build_main() {
    stage=$(mktemp -d)
    scripts=$(mktemp -d)
    plist=$(mktemp)

    # Map src/ to install paths:
    #   src/usr/... → /usr/...   (binaries land at /usr/local/sbin, /usr/local/bin)
    #   src/...     → /usr/local/...   (everything else follows OPNsense prefix)
    find net/cloudflare-zt/src -type f ! -name '.gitkeep' | while read -r src; do
        rel="${src#net/cloudflare-zt/src/}"
        case "$rel" in
            usr/*) dst="$stage/$rel" ;;
            *)     dst="$stage/usr/local/$rel" ;;
        esac
        install -D -m 0644 "$src" "$dst"
    done
    chmod 0755 "$stage/usr/local/sbin/cfzt-warp" \
               "$stage/usr/local/bin/cloudflared"
    find "$stage/usr/local/opnsense/scripts" -name '*.py' -exec chmod 0755 {} \;

    find "$stage" -type f | sed "s|$stage/||" | sort > "$plist"
    flatsize=$(find "$stage" -type f | xargs stat -f '%z' | awk '{sum+=$1} END{print sum+0}')

    cat > "$scripts/pre-deinstall" <<'SH'
#!/bin/sh
/usr/local/sbin/configctl cloudflarezt stop 2>/dev/null || true
/usr/local/sbin/configctl cloudflarezt stopmonitor 2>/dev/null || true
/usr/local/sbin/configctl cloudflarezt removedns 2>/dev/null || true
for iface in $(ifconfig -l | tr ' ' '\n' | grep '^cfzt'); do
    ifconfig "$iface" destroy 2>/dev/null || true
done
rm -f /var/run/cfzt-*.pid /var/run/cfzt-monitor.pid /var/run/cfzt-iface-*
SH

    cat > "$scripts/post-deinstall" <<'SH'
#!/bin/sh
/usr/sbin/unbound-control reload 2>/dev/null || true
SH

    cat > "$stage/+MANIFEST" <<EOF
name: "os-cloudflare-zt"
version: "${VERSION}"
origin: "net/os-cloudflare-zt"
comment: "Cloudflare Zero Trust VPN plugin for OPNsense"
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

    pkg create -M "$stage/+MANIFEST" -r "$stage" -p "$plist" -s "$scripts" -o "$DIST/"
    rm -rf "$stage" "$scripts" "$plist"
    echo "==> Built: $DIST/os-cloudflare-zt-${VERSION}.pkg"
}

# ── os-repo-aendryn (bootstrap) ──────────────────────────────────────────
build_bootstrap() {
    stage=$(mktemp -d)
    plist=$(mktemp)

    install -D -m 0644 net/repo-bootstrap/src/usr/local/etc/pkg/repos/aendryn.conf \
        "$stage/usr/local/etc/pkg/repos/aendryn.conf"
    install -D -m 0644 net/repo-bootstrap/src/usr/local/share/aendryn/pubkey.rsa \
        "$stage/usr/local/share/aendryn/pubkey.rsa"

    find "$stage" -type f | sed "s|$stage/||" | sort > "$plist"
    flatsize=$(find "$stage" -type f | xargs stat -f '%z' | awk '{sum+=$1} END{print sum+0}')

    cat > "$stage/+MANIFEST" <<EOF
name: "os-repo-aendryn"
version: "1.0.0"
origin: "net/os-repo-aendryn"
comment: "aendryn OPNsense plugin repository configuration"
arch: "freebsd:*:*"
www: "https://github.com/aendryn/cf-masque-opnsense"
maintainer: "aendryn@github"
prefix: "/"
flatsize: ${flatsize}
EOF

    pkg create -M "$stage/+MANIFEST" -r "$stage" -p "$plist" -o "$DIST/"
    rm -rf "$stage" "$plist"
    echo "==> Built: $DIST/os-repo-aendryn-1.0.0.pkg"
}

build_main
build_bootstrap

# Sign and publish the repo
cp "$DIST"/*.pkg "$REPO/All/"
pkg repo "$REPO" "$(pwd)/.ci-signing.key"

echo "==> Repo contents:"
ls -la "$REPO/All/"
ls -la "$REPO/"
