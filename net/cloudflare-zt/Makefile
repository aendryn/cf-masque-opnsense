PLUGIN_NAME=		cloudflare-zt
PLUGIN_VERSION=		1.0.0
PLUGIN_REVISION=	0
PLUGIN_COMMENT=		Cloudflare Zero Trust VPN
PLUGIN_DEPENDS=		wireguard-tools py311-cryptography

PLUGIN_WWW=		https://github.com/opnsense/plugins
PLUGIN_MAINTAINER=	plugins@opnsense.org

# Bundled third-party binaries — update CLOUDFLARED_VERSION when upgrading.
# Both are pre-built for FreeBSD amd64 and shipped inside the package so
# no external fetches or toolchains are needed on the target OPNsense box.
CLOUDFLARED_VERSION=	2025.1.0
CLOUDFLARED_URL=	https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-freebsd-amd64

CFZT_WARP_BIN=		${.CURDIR}/src/usr/local/sbin/cfzt-warp
CLOUDFLARED_BIN=	${.CURDIR}/src/usr/local/bin/cloudflared

# build-daemon: run this in CI before 'make package'.
# Compiles cfzt-warp from source and downloads the pinned cloudflared release.
build-daemon:
	@echo "==> Building cfzt-warp ${PLUGIN_VERSION} for FreeBSD amd64..."
	@mkdir -p ${.CURDIR}/src/usr/local/sbin ${.CURDIR}/src/usr/local/bin
	@cd ${.CURDIR}/../../go/cfzt-warp && \
		GOOS=freebsd GOARCH=amd64 CGO_ENABLED=0 go build \
		-ldflags="-s -w -X main.Version=${PLUGIN_VERSION}" \
		-o ${CFZT_WARP_BIN} .
	@echo "==> Downloading cloudflared ${CLOUDFLARED_VERSION}..."
	@fetch -q -o ${CLOUDFLARED_BIN} ${CLOUDFLARED_URL} 2>/dev/null || \
		curl -fsSL -o ${CLOUDFLARED_BIN} ${CLOUDFLARED_URL}
	@chmod 0755 ${CFZT_WARP_BIN} ${CLOUDFLARED_BIN}
	@sha256 ${CFZT_WARP_BIN} ${CLOUDFLARED_BIN}
	@echo "==> build-daemon complete."

# Fail fast if binaries are missing — prevents silently packaging without them.
pre-install:
	@if [ ! -x ${CFZT_WARP_BIN} ]; then \
		echo "ERROR: ${CFZT_WARP_BIN} not found. Run 'make build-daemon' first."; \
		false; \
	fi
	@if [ ! -x ${CLOUDFLARED_BIN} ]; then \
		echo "ERROR: ${CLOUDFLARED_BIN} not found. Run 'make build-daemon' first."; \
		false; \
	fi

.include "../../Mk/plugins.mk"
