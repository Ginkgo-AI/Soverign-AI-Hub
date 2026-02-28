#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${PROJECT_DIR}/deploy/airgap"

echo "========================================="
echo "  Building Air-Gap Deployment Bundle"
echo "========================================="

# Parse args
MODELS=""
OUTPUT_FILE="sovereign-ai-hub-airgap.tar.gz"

while [[ $# -gt 0 ]]; do
    case $1 in
        --models) MODELS="$2"; shift 2 ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

mkdir -p "$OUTPUT_DIR"

# 1. Build all container images
echo ""
echo "Step 1: Building container images..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" build

# 2. Save images as tar files
echo ""
echo "Step 2: Exporting container images..."
mkdir -p "$OUTPUT_DIR/container-images"

for service in gateway frontend workers; do
    IMAGE_NAME="local_ai-${service}:latest"
    echo "  Saving $IMAGE_NAME..."
    docker save "$IMAGE_NAME" -o "$OUTPUT_DIR/container-images/${service}.tar"
done

# Also save infrastructure images
for image in postgres:16-alpine qdrant/qdrant:v1.13.2 redis:7-alpine; do
    SAFE_NAME=$(echo "$image" | tr '/:' '-')
    echo "  Saving $image..."
    docker pull "$image"
    docker save "$image" -o "$OUTPUT_DIR/container-images/${SAFE_NAME}.tar"
done

# 3. Copy configuration
echo ""
echo "Step 3: Copying configuration..."
cp "$PROJECT_DIR/docker-compose.yml" "$OUTPUT_DIR/"
cp "$PROJECT_DIR/.env.example" "$OUTPUT_DIR/"

# 4. Generate SBOM
echo ""
echo "Step 4: Generating SBOM..."
if command -v syft &> /dev/null; then
    for tar_file in "$OUTPUT_DIR/container-images"/*.tar; do
        BASENAME=$(basename "$tar_file" .tar)
        syft "$tar_file" -o spdx-json > "$OUTPUT_DIR/${BASENAME}-sbom.json" 2>/dev/null || true
    done
    echo "  SBOMs generated"
else
    echo "  WARNING: syft not installed, skipping SBOM generation"
fi

# 5. Create install script
cat > "$OUTPUT_DIR/install.sh" << 'INSTALL_EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "Installing Sovereign AI Hub (air-gapped)..."

# Load container images
for tar_file in container-images/*.tar; do
    echo "  Loading $(basename "$tar_file")..."
    docker load -i "$tar_file"
done

# Setup env
if [ ! -f .env ]; then
    cp .env.example .env
fi

echo ""
echo "Installation complete. Run: docker compose up -d"
INSTALL_EOF
chmod +x "$OUTPUT_DIR/install.sh"

# 6. Package everything
echo ""
echo "Step 5: Creating bundle..."
tar -czf "$PROJECT_DIR/$OUTPUT_FILE" -C "$OUTPUT_DIR" .

BUNDLE_SIZE=$(du -sh "$PROJECT_DIR/$OUTPUT_FILE" | cut -f1)
echo ""
echo "========================================="
echo "  Bundle created: $OUTPUT_FILE ($BUNDLE_SIZE)"
echo "========================================="
