#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# SBOM (Software Bill of Materials) Generator — Phase 6
#
# Generates a CycloneDX-format SBOM for all project dependencies:
#   - Python (pip) dependencies from gateway and workers
#   - Node.js (npm) dependencies from frontend
#
# Output: reports/sbom/
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/reports/sbom"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

mkdir -p "$REPORT_DIR"

echo "========================================"
echo "  Sovereign AI Hub — SBOM Generator"
echo "  $(date)"
echo "========================================"
echo ""

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
echo "[1/3] Collecting Python dependencies..."

PIP_FREEZE_FILE="$REPORT_DIR/python-packages.txt"
if command -v pip &>/dev/null; then
    pip freeze 2>/dev/null > "$PIP_FREEZE_FILE" || true
elif [ -f "$PROJECT_ROOT/gateway/requirements.txt" ]; then
    cp "$PROJECT_ROOT/gateway/requirements.txt" "$PIP_FREEZE_FILE"
else
    echo "# No pip available and no requirements.txt found" > "$PIP_FREEZE_FILE"
fi

# Build CycloneDX JSON for Python
PYTHON_SBOM="$REPORT_DIR/sbom-python.json"
{
    echo '{'
    echo '  "bomFormat": "CycloneDX",'
    echo '  "specVersion": "1.5",'
    echo '  "serialNumber": "urn:uuid:'$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "00000000-0000-0000-0000-000000000000")'",'
    echo "  \"version\": 1,"
    echo "  \"metadata\": {"
    echo "    \"timestamp\": \"$TIMESTAMP\","
    echo '    "component": {'
    echo '      "type": "application",'
    echo '      "name": "sovereign-ai-hub",'
    echo '      "version": "0.1.0"'
    echo '    }'
    echo '  },'
    echo '  "components": ['

    first=true
    while IFS= read -r line; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" == \#* ]] && continue

        # Parse package==version or package>=version
        pkg_name=$(echo "$line" | sed -E 's/([a-zA-Z0-9_.-]+).*/\1/')
        pkg_version=$(echo "$line" | sed -E 's/[a-zA-Z0-9_.-]+=+//' | sed -E 's/[><=!].*//')

        if [ "$first" = true ]; then
            first=false
        else
            echo ','
        fi

        cat <<COMPONENT
    {
      "type": "library",
      "name": "$pkg_name",
      "version": "$pkg_version",
      "purl": "pkg:pypi/$pkg_name@$pkg_version",
      "scope": "required"
    }
COMPONENT
    done < "$PIP_FREEZE_FILE"

    echo ''
    echo '  ]'
    echo '}'
} > "$PYTHON_SBOM"

echo "  -> $PYTHON_SBOM"

# ---------------------------------------------------------------------------
# Node.js dependencies
# ---------------------------------------------------------------------------
echo "[2/3] Collecting Node.js dependencies..."

NODE_SBOM="$REPORT_DIR/sbom-frontend.json"
if [ -d "$PROJECT_ROOT/frontend" ] && [ -f "$PROJECT_ROOT/frontend/package.json" ]; then
    cd "$PROJECT_ROOT/frontend"

    NPM_LIST_FILE="$REPORT_DIR/npm-packages.json"
    if command -v npm &>/dev/null; then
        npm list --json --all 2>/dev/null > "$NPM_LIST_FILE" || echo '{}' > "$NPM_LIST_FILE"
    else
        echo '{}' > "$NPM_LIST_FILE"
    fi

    # Build CycloneDX JSON for Node
    {
        echo '{'
        echo '  "bomFormat": "CycloneDX",'
        echo '  "specVersion": "1.5",'
        echo '  "serialNumber": "urn:uuid:'$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "00000000-0000-0000-0000-000000000001")'",'
        echo "  \"version\": 1,"
        echo "  \"metadata\": {"
        echo "    \"timestamp\": \"$TIMESTAMP\","
        echo '    "component": {'
        echo '      "type": "application",'
        echo '      "name": "sovereign-ai-hub-frontend",'
        echo '      "version": "0.1.0"'
        echo '    }'
        echo '  },'
        echo '  "components": ['

        # Extract top-level deps from package.json
        first=true
        if command -v node &>/dev/null; then
            node -e "
                const pkg = require('./package.json');
                const deps = { ...pkg.dependencies, ...pkg.devDependencies };
                Object.entries(deps).forEach(([name, version]) => {
                    console.log(name + '==' + version.replace(/[\^~>=<]/g, ''));
                });
            " 2>/dev/null | while IFS= read -r line; do
                pkg_name=$(echo "$line" | cut -d= -f1)
                pkg_version=$(echo "$line" | sed 's/.*==//')
                if [ "$first" = true ]; then
                    first=false
                else
                    echo ','
                fi
                cat <<COMPONENT
    {
      "type": "library",
      "name": "$pkg_name",
      "version": "$pkg_version",
      "purl": "pkg:npm/$pkg_name@$pkg_version",
      "scope": "required"
    }
COMPONENT
            done
        fi

        echo ''
        echo '  ]'
        echo '}'
    } > "$NODE_SBOM"

    echo "  -> $NODE_SBOM"
    cd "$PROJECT_ROOT"
else
    echo "  -> Skipped (no frontend/package.json found)"
fi

# ---------------------------------------------------------------------------
# Combined summary
# ---------------------------------------------------------------------------
echo "[3/3] Generating summary report..."

SUMMARY="$REPORT_DIR/sbom-summary.txt"
{
    echo "======================================"
    echo "  Sovereign AI Hub — SBOM Summary"
    echo "  Generated: $TIMESTAMP"
    echo "======================================"
    echo ""
    echo "Python packages:"
    wc -l < "$PIP_FREEZE_FILE" | xargs -I{} echo "  {} packages"
    echo ""
    echo "Format: CycloneDX 1.5 (JSON)"
    echo ""
    echo "Files:"
    echo "  $PYTHON_SBOM"
    [ -f "$NODE_SBOM" ] && echo "  $NODE_SBOM"
    echo "  $PIP_FREEZE_FILE"
    echo ""
    echo "To validate: npx @cyclonedx/cyclonedx-cli validate --input-file $PYTHON_SBOM"
} > "$SUMMARY"

cat "$SUMMARY"
echo ""
echo "SBOM generation complete. Files written to: $REPORT_DIR"
