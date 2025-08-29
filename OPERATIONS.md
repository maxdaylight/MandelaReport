# Operations & Runbook

Quick run (Docker Compose)

```bash
# Build and start the stack
docker compose build
docker compose up -d
# Open http://localhost:8081/docs
```

Backups and DB

- Database path: `./data/mandelareport.sqlite3`.
- Backup suggestion: schedule a cron job or host-level backup that copies `data/mandelareport.sqlite3` to an off-host backup.
- Migrations: consider introducing Alembic for schema migrations before major changes.

Healthchecks & monitoring

- Add a simple /health endpoint and run a container-level healthcheck in production.
- Configure logging (structured JSON) and integrate with a log aggregator for production.

Scaling notes

- The service is single-process; to scale horizontally use multiple app replicas behind a reverse proxy and an external SQLite alternative (Postgres) if concurrency increases.
