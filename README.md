# license-ops-automation

A self-hosted [n8n](https://n8n.io) automation suite for SaaS license operations at a fictional company, **Northwind Media**: user and activity auditing, spend and budget reporting, contract intake with RAG, and renewal alerts.

This is a portfolio project. **All data is synthetic** and the vendor APIs are mocks, so you need no accounts or API keys to run it.

See [docs/demo.md](docs/demo.md) for a walkthrough, and `docs/` for one page per workflow.

## Quickstart

Requirements: Docker with Compose, Python 3.12+.

```bash
git clone https://github.com/renehiler-rgb/license-ops-automation.git
cd license-ops-automation

# 1. Configuration
cp .env.example .env
#    Edit .env and replace every "change-me". Any values work for the mock vendor
#    keys and secrets. Use a long random string for N8N_ENCRYPTION_KEY,
#    for example `openssl rand -hex 32`.

# 2. Generate the synthetic data (standard library only)
python3 scripts/generate_data.py

# 3. Start the stack (n8n, Postgres + pgvector, mock vendor APIs)
docker compose up -d

# 4. Load employees, tools, contracts and budgets into Postgres
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/load_data.py

# 5. Check it works
curl -s localhost:8000/health
```

Then open <http://localhost:5678>, create the local owner account, and import the files in `workflows/` (Workflows → Import from file).

All services bind to `127.0.0.1` only. Nothing is exposed to your network.

The mock vendor APIs need credentials. n8n credentials for them (API keys, OAuth2 client id and secret) use the values from your `.env`; the OAuth2 token URL is `http://mock-vendors:8000/oauth/token`.

### Optional: local LLM (Ollama)

Contract intake uses embeddings from a local Ollama model. See [docs/ollama-setup.md](docs/ollama-setup.md). The other workflows do not need it.

## Useful commands

```bash
docker compose logs -f n8n
docker compose exec postgres psql -U licenseops -d licenseops
docker compose down        # stop (keeps data)
docker compose down -v     # stop and DELETE the Postgres volume
```

## Layout

| Path | Contents |
|---|---|
| `docker-compose.yml` | n8n, Postgres (pgvector), mock vendor API |
| `db/init/` | SQL schema, views, seed config (applied in filename order) |
| `mock-vendors/` | FastAPI app that imitates vendor APIs |
| `scripts/` | Data generation and loading, secret scan |
| `workflows/` | Exported n8n workflows (no secrets) |
| `sample-contracts/` | Synthetic contract PDFs |
| `docs/` | Documentation |

## Privacy design

- User and activity data never leaves the machine; it is never sent to an external LLM.
- Only contract text may be sent to an external LLM, and all contracts are synthetic.
- Feature flags and thresholds live in the `app_config` table, not in environment variables.
- Database writes are idempotent (`ON CONFLICT`), so re-running is safe.
