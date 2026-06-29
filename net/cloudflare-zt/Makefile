PLUGIN_NAME=		cloudflare-zt
PLUGIN_VERSION=		1.0.0
PLUGIN_REVISION=	0
PLUGIN_COMMENT=		Cloudflare Zero Trust VPN
PLUGIN_DEPENDS=		cloudflared wireguard-tools

PLUGIN_WWW=		https://github.com/opnsense/plugins

PLUGIN_MAINTAINER=	plugins@opnsense.org

BUILD_GO_DAEMON=	yes

.if defined(BUILD_GO_DAEMON)
pre-install:
	@echo "Building cfzt-warp daemon..."
	@cd ${.CURDIR}/../../go/cfzt-warp && \
		GOOS=freebsd GOARCH=amd64 go build \
		-ldflags="-s -w -X main.Version=${PLUGIN_VERSION}" \
		-o ${.CURDIR}/src/usr/local/sbin/cfzt-warp .
.endif

.include "../../Mk/plugins.mk"
