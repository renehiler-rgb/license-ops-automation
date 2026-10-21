# CLAUDE.md — license-ops-automation

Copy this file to the repo root. It gives Claude Code the project context.

## What this repo is
A self-hosted n8n automation suite for SaaS license operations at a fictional company, **Northwind Media**: user and activity auditing, spend and budget reporting, contract intake with RAG, and renewal alerts. It is a public portfolio project. All data is synthetic.

## Machine
- Ubuntu, i9-9900K, 64 GB RAM, RTX 3090. Docker with NVIDIA Container Toolkit.
- Ollama runs on the host (systemd service), models stored on `/mnt/models`. From containers it is reached at `http://host.docker.internal:11434`.
- n8n is only reachable via localhost / Tailscale. Never bind services to 0.0.0.0 on the host and never expose ports publicly.

## Stack
- `docker-compose.yml`: `n8n`, `postgres` (image `pgvector/pgvector:pg16`), `mock-vendors` (FastAPI, Python 3.12).
- Postgres database `licenseops` holds all app data. Schema in `db/init/*.sql`, applied in filename order.
- n8n workflows are exported to `workflows/*.json`.

## Layout
```
docker-compose.yml   .env.example   .gitignore   README.md   CLAUDE.md
db/init/             SQL schema, views, seed config
mock-vendors/        FastAPI app + Dockerfile
scripts/             generate_data.py, make_contract_pdfs.py, load_data.py, scan_secrets.sh
data/                generated (gitignored except data/README.md)
sample-contracts/    generated PDFs (committed, synthetic)
workflows/           exported n8n JSON, no secrets, no IDs of real accounts
docs/                one .md per workflow, architecture, images/
plan/                build plan (day files)
```

## Rules
- Synthetic data only. Never add real company names, people, or credentials.
- Every DB write is idempotent (`ON CONFLICT`). Re-runs must not duplicate.
- Feature flags and thresholds come from the `app_config` table, not environment variables.
- User/activity data never goes to an external LLM. Contract text may go to Anthropic.
- Before committing workflow JSON, run `scripts/scan_secrets.sh`.
- Python: readable, commented, beginner-friendly (the owner is learning Python). Type hints welcome, no clever one-liners.
- Prefer small commits with clear messages.

## Useful commands
```
docker compose up -d
docker compose logs -f n8n
docker compose exec postgres psql -U licenseops -d licenseops
python3 scripts/generate_data.py && python3 scripts/load_data.py
curl -s localhost:8000/health
```
