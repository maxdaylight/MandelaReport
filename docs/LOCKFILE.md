# Lockfile Generation

This repository includes `requirements.lock.txt` as the canonical, Linux-built lockfile. It was generated on an Ubuntu runner (WSL) to avoid Windows-specific wheels.

To regenerate locally on WSL/Ubuntu:

```bash
cd /mnt/c/tmp/MandelaReport-lock   # copy of repo accessible to WSL
python3 -m venv .venv-lock
source .venv-lock/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip freeze > requirements.lock.txt
```

Alternatively, run the GitHub Actions workflow `generate-lockfile` which will produce and upload an artifact or open a PR via `update-lockfile-pr`.
