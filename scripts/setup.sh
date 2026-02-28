#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "  Sovereign AI Hub — Development Setup"
echo "========================================="

# Check dependencies
for cmd in docker git; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd is required but not installed."
        exit 1
    fi
done

# Check Docker is running
if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running."
    exit 1
fi

# Create .env if not exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Creating .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  -> Edit .env to customize settings"
fi

# Determine backend profile
GPU_AVAILABLE=false
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    GPU_AVAILABLE=true
fi

echo ""
echo "System detection:"
echo "  GPU available: $GPU_AVAILABLE"

PROFILE="cpu"
if [ "$GPU_AVAILABLE" = true ]; then
    echo "  Using profile: gpu (vLLM)"
    PROFILE="gpu"
else
    echo "  Using profile: cpu (llama.cpp)"
fi

# Start infrastructure services first
echo ""
echo "Starting infrastructure (postgres, qdrant, redis)..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d postgres qdrant redis

echo ""
echo "Waiting for services to be healthy..."
sleep 5

# Check if a model is available
if [ ! -f "$PROJECT_DIR/models/llm/default.gguf" ] && [ "$PROFILE" = "cpu" ]; then
    echo ""
    echo "WARNING: No model found at models/llm/default.gguf"
    echo "  Run: ./scripts/download-models.sh --model llama-3.1-8b-instruct-q4"
    echo ""
fi

echo ""
echo "Starting application services..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" --profile "$PROFILE" up -d

echo ""
echo "========================================="
echo "  Setup complete!"
echo ""
echo "  Frontend:  http://localhost:3000"
echo "  API:       http://localhost:8888"
echo "  API Docs:  http://localhost:8888/docs"
echo "  Qdrant:    http://localhost:6333/dashboard"
echo "========================================="
