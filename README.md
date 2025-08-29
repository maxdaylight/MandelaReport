
# MandelaReport

Compare a webpage's live content vs historical snapshots from the Wayback Machine. See word-level diffs and a human-friendly summary (LLM optional).

## Features

- Robots-aware live fetch (HTML only, size caps)
- Wayback snapshot selection between dates or N evenly spaced picks
- Clean text extraction and word-level diffs (insertions/removals highlighted)
- Narrative summary via local llama.cpp (TinyLlama), with rule-based fallback
- SQLite storage, Dockerized, HTTP UI at `/report/{id}`

## Quick start (Windows PowerShell)

```powershell
# Optional: put a GGUF model into .\models (see LLM section)
docker compose build
docker compose up -d
Start-Process http://localhost:8081/docs
```

## Quick start (Debian CT in Proxmox)

- Create a Debian CT with nesting + keyctl enabled.
- Install Docker in the CT.

```bash
git clone <your-repo> mandelareport
cd mandelareport
docker compose build
docker compose up -d
# Open http://<CT-IP>:8081/docs
```

## Using it

- POST `/diff` with:

```json
{ "url": "https://example.com/", "since": "2020-01-01", "until": "2025-01-01", "snapshots": 3 }
```

- Then open `/report/{report_id}`.

## Configuration

Environment variables (see docker-compose.yml):

- `APP__USER_AGENT` — identify your bot, include contact email.
- `APP__REQUEST_TIMEOUT` — seconds (default 15).
- `APP__MAX_RESPONSE_MB` — default 5 MB.
- `APP__OBEY_ROBOTS` — true to require robots permission for live fetch.
- `APP__ALLOW_WAYBACK` — true to use Wayback.
- `APP__SUMMARY_PROVIDER` — auto|llm|rule.
- `APP__LLM_BASE_URL` — OpenAI-compatible base, defaults to llama.cpp server.

Data persists in `./data/mandelareport.sqlite3`.

## LLM (optional)

- Place a GGUF model file into `./models` (e.g., TinyLlama 1.1B Chat Q4_K_M).
- The compose file starts the bundled `llama.cpp` server image and mounts your local `./models` directory into the container at `/models`.

Important: For security and reproducibility we no longer download models at image build time. Do not provide credentials to the build process. The preferred workflow is to pre-download the model into `./models` and mount it read-only into the `llm` service. If you absolutely must download at runtime, you can provide `HF_REPO`, `HF_FILE` and `HF_TOKEN` as environment variables to the `llm` service; the container entrypoint will attempt a runtime fetch.

Model options:

- Manually place a file at `./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`.
- Or use the provided scripts to fetch a model locally and then start the compose stack (preferred):

Windows PowerShell:

```powershell
pip install -U huggingface_hub
./scripts/fetch-model.ps1 -UseCli -Repo "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF" -Filename "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf" -OutPath "../models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
```

Linux/macOS:

```bash
# Example: fetch model locally then start compose
pipx install huggingface_hub || pip install -U huggingface_hub
REPO=TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF \
FILENAME=tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
bash scripts/fetch-model.sh ./models/${FILENAME}
docker compose build
docker compose up -d
```

Git LFS:

- `.gitattributes` is configured to track `*.gguf` with Git LFS. Run `git lfs install` once in your repo if you plan to commit models.

## Notes

- Live fetch obeys robots.txt; if disallowed, we only use Wayback snapshots.
- HTML-only focus for reliability and low resource usage.

## License

Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
