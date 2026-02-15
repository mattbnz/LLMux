#!/bin/bash
set -e

handle_err() {
	echo "Failed at line $BASH_LINENO"
	echo "sleeping 120s for debug"
	sleep 120
}

trap handle_err ERR

if [ ! -z "$SKIP_TAILSCALE" ]; then
    exit
fi

TS_STATE_DIR="${TS_STATE_DIR:/tmp}"
export TS_STATE_DIR

# Start tailscaled in userspace networking mode (no TUN required)
echo "Starting tailscaled daemon..."
tailscaled \
    --state="${TS_STATE_DIR}/tailscaled.state" \
		--statedir="${TS_STATE_DIR}" \
    --tun=userspace-networking \
    --socks5-server=localhost:1055 \
    --outbound-http-proxy-listen=localhost:1056 &

# Wait for tailscaled socket to be ready
echo "Waiting for tailscaled to be ready..."
for i in {1..30}; do
    if [ -S /var/run/tailscale/tailscaled.sock ]; then
        break
    fi
    sleep 0.5
done

# Authenticate with Tailscale
if [ -n "${TS_AUTHKEY}" ]; then
    # Static auth key method
    echo "Authenticating with Tailscale using static auth key..."
    tailscale up \
        --authkey="${TS_AUTHKEY}" \
        --hostname="${TS_HOSTNAME}" \
        --accept-routes=false \
        --reset
elif [ -n "${TS_CLIENT_ID}" ] && [ -n "${TS_AUD}" ] && [ -n "${TS_TAGS}" ]; then
    # OIDC authentication via fly.io
    echo "Authenticating with Tailscale using fly.io OIDC..."

    # Check if fly.io API socket exists
    if [ ! -S "/.fly/api" ]; then
        echo "ERROR: fly.io API socket not found at /.fly/api"
        echo "OIDC authentication is only available when running on fly.io"
        exit 1
    fi

    # Fetch OIDC token from fly.io (returns raw JWT)
    echo "Fetching OIDC token from fly.io..."
    OIDC_TOKEN=$(curl --silent --fail --unix-socket /.fly/api \
        -X POST "http://localhost/v1/tokens/oidc" \
        --data "{\"aud\":\"${TS_AUD}\"}")

    if [ -z "${OIDC_TOKEN}" ]; then
        echo "ERROR: Failed to fetch OIDC token from fly.io"
        exit 1
    fi

    echo "OIDC token obtained successfully"

    # Authenticate with Tailscale using OIDC token
    tailscale up \
        --client-id="${TS_CLIENT_ID}" \
        --id-token="${OIDC_TOKEN}" \
        --advertise-tags="${TS_TAGS}" \
        --hostname="${TS_HOSTNAME}" \
        --accept-routes=false \
        --reset
else
    echo "ERROR: Tailscale authentication not configured"
    echo ""
    echo "Configure one of the following:"
    echo "  1. TS_AUTHKEY - Static auth key from https://login.tailscale.com/admin/settings/keys"
    echo "  2. TS_CLIENT_ID, TS_AUD, and TS_TAGS - For fly.io OIDC authentication"
    exit 1
fi

# Wait for Tailscale to be connected
echo "Waiting for Tailscale connection..."
for i in {1..30}; do
    if tailscale ip -4 >/dev/null 2>&1; then
        echo "Tailscale connected!"
        tailscale ip -4
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Tailscale failed to connect"
        tailscale status
        exit 1
    fi
    sleep 1
done

# Show Tailscale status
tailscale status

# Configure tailscale serve to expose the proxy
# --accept-app-caps allows tagged devices with the capability to authenticate
if [ ! -z "${TS_SERVE_PORT}" ]; then 
	echo "Configuring tailscale serve for port ${TS_SERVE_PORT}..."
	tailscale serve --bg --https=443 --set-path=/ --accept-app-caps="${TS_APP_CAPABILITY}" "http://localhost:${TS_SERVE_PORT}"

	# Show the serve configuration
	echo "Tailscale serve configured:"
	tailscale serve status

	# Get the Tailscale URL
	TS_URL=$(tailscale status --json | grep -o '"DNSName":"[^"]*"' | head -1 | cut -d'"' -f4 | sed 's/\.$//')
	if [ -n "${TS_URL}" ]; then
			echo ""
			echo "==========================================="
			echo "Application is available at: https://${TS_URL}"
			echo "==========================================="
			echo ""
	fi
fi
