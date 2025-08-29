#!/usr/bin/env bash
set -euo pipefail
REPO="
: ${REPO:=TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF}
"
FILENAME="${FILENAME:-tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf}"
OUT_PATH="${1:-../models/$FILENAME}"
mkdir -p "$(dirname "$OUT_PATH")"

if command -v huggingface-cli >/dev/null 2>&1; then
	echo "Using hf to download $REPO $FILENAME"
	hf download "$REPO" "$FILENAME" --local-dir "$(dirname "$OUT_PATH")"
else
	echo "hf not found. Please install it or download manually."
	exit 1
fi
echo "Downloaded to $(dirname "$OUT_PATH")/$FILENAME"
