#!/bin/bash
set -e

# Configuration
DATA_DIR="/data"
LLMUX_DIR="${DATA_DIR}/.llmux"
PORT="${PORT:-8081}"
export TS_HOSTNAME="${TS_HOSTNAME:-llmux}"
export TS_STATE_DIR="${DATA_DIR}/tailscale"

# Create data directories
mkdir -p "${LLMUX_DIR}"
mkdir -p "${LLMUX_DIR}/chatgpt"
mkdir -p "${TS_STATE_DIR}"

# Set HOME to data directory so LLMux stores tokens/keys in the volume
export HOME="${DATA_DIR}"

# Export storage paths for LLMux (point to data volume)
export TOKEN_FILE="${LLMUX_DIR}/tokens.json"
export API_KEYS_FILE="${LLMUX_DIR}/api_keys.json"
export USAGE_DB_FILE="${LLMUX_DIR}/usage.db"
export CHATGPT_TOKEN_FILE="${LLMUX_DIR}/chatgpt/tokens.json"
export STREAM_TRACE_DIR="${DATA_DIR}/stream_traces"

echo "Starting LLMux with Tailscale..."
echo "  Data directory: ${DATA_DIR}"
echo "  HOME: ${HOME}"
echo "  TOKEN_FILE: ${TOKEN_FILE}"
echo "  LOG_LEVEL: ${LOG_LEVEL:-info}"
echo "  Tailscale hostname: ${TS_HOSTNAME}"
echo "  Proxy port: ${PORT}"



if [ "${SKIP_TAILSCALE}" != "true" ] && [ "${SKIP_TAILSCALE}" != "1" ]; then
  echo "Starting tailscale..."
  /tailscale-startup.sh
fi

# Check if we have authentication configured
if [ ! -f "${TOKEN_FILE}" ]; then
    echo "NOTE: No tokens.json found - authenticate via the web UI at https://${TS_URL}/ui/"
fi

# Start LLMux in headless mode
echo "Starting LLMux proxy on port ${PORT}..."
exec python cli.py --headless
