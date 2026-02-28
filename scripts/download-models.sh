#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$(dirname "$SCRIPT_DIR")/models"

usage() {
    echo "Usage: $0 --model <model-name>"
    echo ""
    echo "Available models:"
    echo "  llama-3.1-8b-instruct-q4     General chat (6GB VRAM, laptop-friendly)"
    echo "  llama-3.1-70b-instruct-q4    General chat (40GB VRAM, production)"
    echo "  qwen2.5-coder-32b-q4         Code generation (20GB VRAM)"
    echo "  nomic-embed-text             Embedding model (CPU, ~500MB)"
    echo "  mistral-nemo-12b-q4          Efficient chat + tool calling (8GB VRAM)"
    echo ""
    echo "Example:"
    echo "  $0 --model llama-3.1-8b-instruct-q4"
    exit 1
}

MODEL=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --model) MODEL="$2"; shift 2 ;;
        *) usage ;;
    esac
done

[ -z "$MODEL" ] && usage

# Check for download tools
DOWNLOADER=""
if command -v huggingface-cli &> /dev/null; then
    DOWNLOADER="hf"
elif command -v wget &> /dev/null; then
    DOWNLOADER="wget"
elif command -v curl &> /dev/null; then
    DOWNLOADER="curl"
else
    echo "ERROR: Need huggingface-cli, wget, or curl"
    exit 1
fi

download_hf() {
    local repo="$1"
    local filename="$2"
    local dest="$3"
    echo "Downloading $repo/$filename -> $dest"
    if [ "$DOWNLOADER" = "hf" ]; then
        huggingface-cli download "$repo" "$filename" --local-dir "$(dirname "$dest")"
    else
        local url="https://huggingface.co/$repo/resolve/main/$filename"
        if [ "$DOWNLOADER" = "wget" ]; then
            wget -O "$dest" "$url"
        else
            curl -L -o "$dest" "$url"
        fi
    fi
}

case "$MODEL" in
    llama-3.1-8b-instruct-q4)
        mkdir -p "$MODEL_DIR/llm"
        echo "Downloading Llama 3.1 8B Instruct Q4_K_M..."
        download_hf \
            "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF" \
            "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf" \
            "$MODEL_DIR/llm/default.gguf"
        echo "Model saved to $MODEL_DIR/llm/default.gguf"
        ;;
    nomic-embed-text)
        mkdir -p "$MODEL_DIR/embedding"
        echo "Downloading nomic-embed-text..."
        download_hf \
            "nomic-ai/nomic-embed-text-v1.5-GGUF" \
            "nomic-embed-text-v1.5.Q8_0.gguf" \
            "$MODEL_DIR/embedding/nomic-embed-text.gguf"
        echo "Model saved to $MODEL_DIR/embedding/nomic-embed-text.gguf"
        ;;
    *)
        echo "Model '$MODEL' not yet configured in download script."
        echo "You can manually download GGUF files to $MODEL_DIR/llm/"
        exit 1
        ;;
esac

echo ""
echo "Download complete. Model ready for use."
