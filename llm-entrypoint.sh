#!/usr/bin/env bash
set -euo pipefail

# Runtime entrypoint for the llama.cpp server image.
# If a model file is already present in /models matching HF_FILE, we start
# the server. Otherwise, if HF_REPO and HF_FILE are provided and HF_TOKEN
# is set, we attempt to download the model at container start (runtime).

HF_REPO=${HF_REPO:-}
HF_FILE=${HF_FILE:-}
HF_TOKEN=${HF_TOKEN:-}

MODEL_PATH="/models/${HF_FILE}"

# Ensure /models exists
mkdir -p /models

if [ -f "${MODEL_PATH}" ]; then
  echo "Model already present: ${MODEL_PATH}"
else
  if [ -n "${HF_REPO}" ] && [ -n "${HF_FILE}" ]; then
    echo "Model not found at ${MODEL_PATH}."
    if [ -n "${HF_TOKEN}" ]; then
      echo "HF_TOKEN provided — attempting runtime download from Hugging Face..."
      # Configure huggingface CLI to use token for this session
      python3 -m pip install --no-cache-dir huggingface_hub || true
      # Use huggingface_hub python API to download
      python3 - <<PY
from huggingface_hub import hf_hub_download
import os
repo = os.environ.get('HF_REPO')
file = os.environ.get('HF_FILE')
out_dir = '/models'
print('Downloading', file, 'from', repo)
try:
    hf_hub_download(repo_id=repo, filename=file, cache_dir=out_dir, local_dir=out_dir, local_dir_use_symlinks=False)
    print('Download complete')
except Exception as e:
    print('Runtime model download failed:', e)
    # Continue anyway — server may still start if models are provided later
PY
    else
      echo "No HF_TOKEN provided. Please mount model into /models or supply HF_TOKEN, HF_REPO, and HF_FILE."
    fi
  else
    echo "No HF_REPO/HF_FILE provided. Please mount model into /models or set HF_REPO/HF_FILE/HF_TOKEN to auto-download."
  fi
fi

# Exec the llama.cpp server entrypoint with forwarded args
exec /usr/local/bin/llama.cpp "$@"
