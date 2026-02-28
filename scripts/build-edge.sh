#!/usr/bin/env bash
# =============================================================================
# Build Edge Agent — Cross-compile for multiple platforms
#
# Produces binaries, packages them with the default config and install script,
# and generates SHA256 checksums.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EDGE_DIR="${PROJECT_DIR}/edge"
OUTPUT_DIR="${PROJECT_DIR}/deploy/edge"
VERSION="0.1.0"

echo "========================================="
echo "  Building Edge Agent v${VERSION}"
echo "========================================="

mkdir -p "$OUTPUT_DIR"

cd "$EDGE_DIR"

# ---------------------------------------------------------------------------
# 1. Cross-compile for all target platforms
# ---------------------------------------------------------------------------
echo ""
echo "Step 1: Cross-compiling..."

PLATFORMS=(
    "linux/amd64"
    "linux/arm64"
    "darwin/amd64"
    "darwin/arm64"
)

for PLATFORM in "${PLATFORMS[@]}"; do
    GOOS="${PLATFORM%/*}"
    GOARCH="${PLATFORM#*/}"
    BINARY_NAME="sovereign-edge-${GOOS}-${GOARCH}"

    echo "  Building ${BINARY_NAME}..."
    CGO_ENABLED=0 GOOS="$GOOS" GOARCH="$GOARCH" \
        go build -ldflags="-s -w" -o "${OUTPUT_DIR}/${BINARY_NAME}" .
done

echo "  Binaries built."

# ---------------------------------------------------------------------------
# 2. Package with install script and default config
# ---------------------------------------------------------------------------
echo ""
echo "Step 2: Packaging..."

cp "${EDGE_DIR}/scripts/install.sh" "${OUTPUT_DIR}/"
chmod +x "${OUTPUT_DIR}/install.sh"

# Create a default config template
cat > "${OUTPUT_DIR}/config.yaml.example" << 'EOF'
# Sovereign Edge Agent Configuration
# ====================================

hub_url: ""
agent_id: ""
agent_name: "edge-agent"
api_key: ""

model_path: "~/.sovereign-edge/models"
data_dir: "~/.sovereign-edge/data"

listen_addr: "0.0.0.0:8899"
sync_interval: "5m"

llm_backend: "embedded"
llm_remote_url: "http://127.0.0.1:8080"
llm_context_size: 4096
llm_threads: 4
llm_gpu_layers: 0
default_model_file: ""
EOF

# ---------------------------------------------------------------------------
# 3. Generate checksums
# ---------------------------------------------------------------------------
echo ""
echo "Step 3: Generating checksums..."

cd "$OUTPUT_DIR"
sha256sum sovereign-edge-* > checksums.sha256
echo "  Checksums written to checksums.sha256"

# ---------------------------------------------------------------------------
# 4. Create distributable archives per platform
# ---------------------------------------------------------------------------
echo ""
echo "Step 4: Creating platform archives..."

for PLATFORM in "${PLATFORMS[@]}"; do
    GOOS="${PLATFORM%/*}"
    GOARCH="${PLATFORM#*/}"
    BINARY_NAME="sovereign-edge-${GOOS}-${GOARCH}"
    ARCHIVE_NAME="sovereign-edge-${VERSION}-${GOOS}-${GOARCH}.tar.gz"

    tar -czf "${ARCHIVE_NAME}" \
        "${BINARY_NAME}" \
        install.sh \
        config.yaml.example

    echo "  ${ARCHIVE_NAME}"
done

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
TOTAL_SIZE=$(du -sh "$OUTPUT_DIR" | cut -f1)
echo ""
echo "========================================="
echo "  Edge Agent build complete (${TOTAL_SIZE})"
echo "  Output: ${OUTPUT_DIR}"
echo "========================================="
