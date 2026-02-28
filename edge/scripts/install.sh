#!/usr/bin/env bash
# =============================================================================
# Sovereign Edge Agent — Installation Script
#
# Installs the sovereign-edge binary, creates config directories, optionally
# sets up a systemd service, and prints getting-started instructions.
# =============================================================================
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
CONFIG_DIR="${HOME}/.sovereign-edge"
BINARY_NAME="sovereign-edge"

echo "========================================="
echo "  Sovereign Edge Agent — Installer"
echo "========================================="
echo ""

# ---- Detect platform --------------------------------------------------------
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    arm64)   ARCH="arm64" ;;
    *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

BINARY_FILE="${BINARY_NAME}-${OS}-${ARCH}"
echo "Platform: ${OS}/${ARCH}"

# ---- Install binary ----------------------------------------------------------
if [ -f "./${BINARY_FILE}" ]; then
    echo "Installing ${BINARY_FILE} to ${INSTALL_DIR}..."
    sudo install -m 755 "./${BINARY_FILE}" "${INSTALL_DIR}/${BINARY_NAME}"
elif [ -f "./bin/${BINARY_FILE}" ]; then
    echo "Installing bin/${BINARY_FILE} to ${INSTALL_DIR}..."
    sudo install -m 755 "./bin/${BINARY_FILE}" "${INSTALL_DIR}/${BINARY_NAME}"
elif [ -f "./${BINARY_NAME}" ]; then
    echo "Installing ${BINARY_NAME} to ${INSTALL_DIR}..."
    sudo install -m 755 "./${BINARY_NAME}" "${INSTALL_DIR}/${BINARY_NAME}"
else
    echo "ERROR: Binary not found. Build first with 'make build-all'."
    exit 1
fi

echo "  Binary installed at: ${INSTALL_DIR}/${BINARY_NAME}"

# ---- Create config directory -------------------------------------------------
echo ""
echo "Creating config directory: ${CONFIG_DIR}"
mkdir -p "${CONFIG_DIR}/data"
mkdir -p "${CONFIG_DIR}/models"

# ---- Generate default config -------------------------------------------------
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
if [ ! -f "${CONFIG_FILE}" ]; then
    AGENT_ID="edge-$(hostname)-$(date +%s | tail -c 6)"
    cat > "${CONFIG_FILE}" << EOF
# Sovereign Edge Agent Configuration
# ====================================

# Hub connection (leave empty for standalone operation)
hub_url: ""
agent_id: "${AGENT_ID}"
agent_name: "$(hostname)-edge"
api_key: ""

# Local paths
model_path: "${CONFIG_DIR}/models"
data_dir: "${CONFIG_DIR}/data"

# Server
listen_addr: "0.0.0.0:8899"

# Sync interval (Go duration: 5m, 1h, etc.)
sync_interval: "5m"

# LLM backend: "embedded" (llama-cli subprocess) or "remote" (HTTP to llama.cpp server)
llm_backend: "embedded"
llm_remote_url: "http://127.0.0.1:8080"
llm_context_size: 4096
llm_threads: 4
llm_gpu_layers: 0

# Default model file (basename of .gguf file in model_path)
default_model_file: ""
EOF
    echo "  Default config written to: ${CONFIG_FILE}"
else
    echo "  Config already exists: ${CONFIG_FILE} (not overwritten)"
fi

# ---- Optional: systemd service -----------------------------------------------
if [ "${1:-}" = "--systemd" ] && command -v systemctl &>/dev/null; then
    echo ""
    echo "Creating systemd service..."

    UNIT_FILE="/etc/systemd/system/sovereign-edge.service"
    sudo tee "${UNIT_FILE}" > /dev/null << EOF
[Unit]
Description=Sovereign AI Hub Edge Agent
After=network.target

[Service]
Type=simple
User=${USER}
ExecStart=${INSTALL_DIR}/${BINARY_NAME} serve
Restart=on-failure
RestartSec=5
Environment=HOME=${HOME}

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable sovereign-edge
    echo "  Service installed. Start with: sudo systemctl start sovereign-edge"
fi

# ---- Done --------------------------------------------------------------------
echo ""
echo "========================================="
echo "  Installation complete!"
echo "========================================="
echo ""
echo "Getting started:"
echo ""
echo "  1. Place a GGUF model file in: ${CONFIG_DIR}/models/"
echo "  2. Update default_model_file in: ${CONFIG_FILE}"
echo "  3. Start the server:    sovereign-edge serve"
echo "  4. Interactive chat:    sovereign-edge chat"
echo "  5. Check status:        sovereign-edge status"
echo ""
echo "  API endpoint: http://localhost:8899/v1/chat/completions"
echo "  Health check: http://localhost:8899/health"
echo ""
echo "To connect to a hub, set hub_url and api_key in the config file."
echo ""
