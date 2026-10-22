# Manual setup

`scripts/bootstrap.sh` does all of this for you. Use this page if you want to understand each step, if the script stops somewhere, or if you do not want a script to touch your n8n.

## 1. Environment
```
cp .env.example .env
python3 scripts/prepare_env.py      # fills every "change-me" with a random value; never changes real values
```
Then put your Slack bot token in `.env` as `SLACK_BOT_TOKEN` ([slack-setup.md](slack-setup.md)). Optional: `ANTHROPIC_API_KEY`, `JIRA_*`, `HOST_*_PORT`.

## 2. Data and stack
```
python3 scripts/generate_data.py                 # synthetic data into data/ (dates depend on today)
docker compose up -d --build                     # n8n, Postgres + pgvector, mock vendor APIs
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/load_data.py            # tools, employees, contracts, budgets into Postgres
.venv/bin/python scripts/make_contract_pdfs.py data/sample-contracts     # PDFs that match this data
```
The database schema (`db/init/*.sql`) is applied automatically the first time Postgres starts on an empty volume.
To start over: `docker compose down -v` deletes the volumes (all data).

## 3. n8n owner account
Open <http://localhost:5678> and create the owner account (n8n asks on first visit).

## 4. Credentials
In n8n: **Credentials, Add credential**. Names matter: the workflow exports refer to them. The Postgres host is `postgres` (the compose service name), not `localhost`.

| Name | Type | Fields |
|---|---|---|
| `licenseops DB` | Postgres | host `postgres`, port 5432, database `licenseops`, user `licenseops`, password = `POSTGRES_PASSWORD`, SSL disabled |
| `HR API Key` | Header Auth | name `X-API-Key`, value = `HR_API_KEY` |
| `Chatterly API Key` | Header Auth | name `X-API-Key`, value = `CHATTERLY_API_KEY` |
| `DesignHub API Key` | Header Auth | name `X-API-Key`, value = `DESIGNHUB_API_KEY` |
| `Code Forge` | OAuth2 API | grant type **Client Credentials**, access token URL `http://mock-vendors:8000/oauth/token`, client id / secret = `CODEFORGE_CLIENT_ID` / `_SECRET`, authentication **Header** |
| `MeetSpace` | OAuth2 API | the same with `MEETSPACE_CLIENT_ID` / `_SECRET` |
| `Intake webhook key` | Header Auth | name `X-Intake-Key`, value = `INTAKE_API_KEY` (protects every webhook) |
| `Slack account` | Slack API | access token = `SLACK_BOT_TOKEN` |
| `Jira SW Cloud account` (optional) | Jira Software Cloud API | email, API token, domain (see [workflow-d-renewal-alerts.md](workflow-d-renewal-alerts.md)) |
| `Anthropic API key` (optional) | Header Auth | name `x-api-key`, value = your key; only used with `llm_provider = "anthropic"` |

Credential IDs: the exports point at fixed IDs. If you create the credentials by hand, n8n gives them new IDs, so after importing a workflow open each node that shows a red credential warning and pick the credential. `bootstrap.sh` avoids this by creating them with the IDs from `scripts/make_n8n_credentials.py`.

## 5. Workflows
Import in this order (Workflows, menu, Import from file): `run-log`, `e-error-handler`, `a-usage-audit`, `b-spend-report`, `d-renewal-alerts`, `f-weekly-health`, `c1-contract-intake`, `c2-ask-contracts`, `r-replay-dead-letter`.
Then open each one and use **Publish** (the schedules and webhooks only run when published). Every workflow has `E - Error handler` set as its error workflow.
The same from the command line:
```
docker compose cp workflows/run-log.json n8n:/tmp/wf.json
docker compose exec n8n n8n import:workflow --input=/tmp/wf.json
docker compose exec n8n n8n publish:workflow --id=<id in the json>
docker compose restart n8n            # published changes take effect after a restart
```

## 6. Ollama (local language model)
See [ollama-setup.md](ollama-setup.md). Pull the two default models: `ollama pull nomic-embed-text` and `ollama pull llama3.1:8b`.

## Reusing an existing n8n volume (maintainer machine)
`docker-compose.yml` uses a normal named volume. To keep an older n8n volume, create `docker-compose.override.yml` (it is gitignored and Compose loads it automatically):
```yaml
volumes:
  n8n_data:
    external: true
    name: n8n_n8n_data
```
The `N8N_ENCRYPTION_KEY` in `.env` must be the same key that volume was created with, or its saved credentials become unreadable.
