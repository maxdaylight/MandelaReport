# Architecture Overview

MandelaReport is a lightweight web service that compares live webpages to historical Wayback Machine snapshots and produces human-friendly summaries.

High level components

- FastAPI app (ASGI) - HTTP endpoints and templates
- Storage - SQLite via `aiosqlite` (data/mandelareport.sqlite3)
- Fetching - `src/core/fetch.py` (live) and `src/core/wayback.py` (wayback selection)
- Extraction - `src/core/extract.py` (selectolax or BeautifulSoup fallback)
- Diffing & summarization - `src/core/diff.py` and `src/core/summarize.py`
- LLM integration - optional llama.cpp server (local) mounted from `./models`
- Background worker - retention/purge logic scheduled at startup

Deployment

- Dockerfile.llm for the LLM service and a docker-compose.yml to run the web app + llm service locally.

Notes

- Models are mounted read-only into the llm container at `/models`.
- `requirements.lock.txt` is the canonical lockfile generated on Linux for reproducible installs.
