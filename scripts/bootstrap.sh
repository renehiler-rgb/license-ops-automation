#!/usr/bin/env bash
# bootstrap.sh - set up the whole stack from a fresh clone.
#
#   cp .env.example .env     (optional: the script creates it if missing)
#   # put your Slack bot token in .env as SLACK_BOT_TOKEN (docs/slack-setup.md)
#   scripts/bootstrap.sh
#
# It: fills the secrets in .env, generates the synthetic data, starts the stack, loads the base data into Postgres,
# creates the n8n owner account, creates the n8n credentials, imports and publishes all workflows.
# Safe to run again: everything is an upsert. Note that importing replaces the workflows with the versions in
# workflows/, so run it again only if you have not changed workflows in the n8n editor (export them first).
# The same steps by hand are in docs/manual-setup.md.

set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
env_value() { grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }

command -v docker >/dev/null || fail "docker is not installed"
docker compose version >/dev/null 2>&1 || fail "docker compose is not available"
command -v python3 >/dev/null || fail "python3 is not installed"

step "1/8 Environment (.env)"
python3 scripts/prepare_env.py
N8N_PORT=$(env_value HOST_N8N_PORT); N8N_PORT=${N8N_PORT:-5678}
POSTGRES_PORT=$(env_value HOST_POSTGRES_PORT); POSTGRES_PORT=${POSTGRES_PORT:-5432}
MOCK_PORT=$(env_value HOST_MOCK_PORT); MOCK_PORT=${MOCK_PORT:-8000}

step "2/8 Synthetic data"
if [ -f data/employees.json ]; then echo "data/ already generated"; else python3 scripts/generate_data.py; fi

step "3/8 Starting the stack (n8n, Postgres + pgvector, mock vendor APIs)"
docker compose up -d --build
printf 'waiting for n8n'
for _ in $(seq 1 90); do
  curl -fs "http://localhost:${N8N_PORT}/healthz" >/dev/null 2>&1 && break
  printf '.'; sleep 2
done
echo
curl -fs "http://localhost:${N8N_PORT}/healthz" >/dev/null || fail "n8n did not start; see: docker compose logs n8n"

step "4/8 Loading tools, employees, contracts and budgets into Postgres"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r scripts/requirements.txt
PGPORT="$POSTGRES_PORT" .venv/bin/python scripts/load_data.py
# The contract dates depend on the day the data was generated, so the sample PDFs are made from THIS data.
.venv/bin/python scripts/make_contract_pdfs.py data/sample-contracts >/dev/null
echo "sample contracts: data/sample-contracts/ (7 PDFs that match your data)"

step "5/8 n8n owner account"
NEEDS_OWNER=$(curl -fs "http://localhost:${N8N_PORT}/rest/settings" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['userManagement']['showSetupOnFirstLoad'])" 2>/dev/null || echo "unknown")
if [ "$NEEDS_OWNER" = "True" ]; then
  OWNER_EMAIL=$(env_value N8N_OWNER_EMAIL); OWNER_PASSWORD=$(env_value N8N_OWNER_PASSWORD)
  curl -fs -X POST "http://localhost:${N8N_PORT}/rest/owner/setup" -H 'Content-Type: application/json' \
    -d "{\"email\":\"${OWNER_EMAIL}\",\"firstName\":\"Owner\",\"lastName\":\"Northwind\",\"password\":\"${OWNER_PASSWORD}\"}" >/dev/null \
    || fail "could not create the n8n owner (open http://localhost:${N8N_PORT} and create it in the browser, then run this script again)"
  echo "created owner ${OWNER_EMAIL} (password is N8N_OWNER_PASSWORD in .env)"
else
  echo "owner already exists"
fi

step "6/8 n8n credentials"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
python3 scripts/make_n8n_credentials.py "$TMP"
docker compose cp "$TMP" n8n:/tmp/credentials.json
docker compose exec -T n8n n8n import:credentials --input=/tmp/credentials.json 2>&1 | grep -v -i "license sdk\|python" || true
docker compose exec -T n8n rm -f /tmp/credentials.json

step "7/8 Workflows"
# The order matters only for readability: every workflow has a fixed id, so they find each other.
ORDER="run-log e-error-handler a-usage-audit b-spend-report d-renewal-alerts f-weekly-health c1-contract-intake c2-ask-contracts r-replay-dead-letter"
IDS=""
for name in $ORDER; do
  docker compose cp "workflows/${name}.json" n8n:/tmp/workflow.json
  docker compose exec -T n8n n8n import:workflow --input=/tmp/workflow.json 2>&1 | grep -i "imported\|error" || true
  IDS="$IDS $(python3 -c "import json,sys; print(json.load(open('workflows/${name}.json'))['id'])")"
done
docker compose exec -T n8n rm -f /tmp/workflow.json
for id in $IDS; do
  # (no "| head": with pipefail a closed pipe would stop the script)
  docker compose exec -T n8n n8n publish:workflow --id="$id" 2>&1 | grep "Publishing workflow" || true
done
docker compose restart n8n >/dev/null
for _ in $(seq 1 60); do curl -fs "http://localhost:${N8N_PORT}/healthz" >/dev/null 2>&1 && break; sleep 2; done

step "8/8 Local language model (Ollama)"
if docker compose exec -T n8n wget -qO- --timeout=5 http://host.docker.internal:11434/api/tags >/tmp/ollama_tags.$$ 2>/dev/null; then
  for model in nomic-embed-text llama3.1:8b; do
    grep -q "\"$model" /tmp/ollama_tags.$$ && echo "ok: $model" || echo "MISSING: run  ollama pull $model   (see docs/ollama-setup.md)"
  done
else
  echo "Ollama is not reachable from the containers at http://host.docker.internal:11434."
  echo "Workflows A and D work without it; B (summary) and C (contracts) need it. See docs/ollama-setup.md."
fi
rm -f /tmp/ollama_tags.$$

cat <<DONE

Done.
  n8n:           http://localhost:${N8N_PORT}   (login: $(env_value N8N_OWNER_EMAIL), password in .env as N8N_OWNER_PASSWORD)
  mock vendors:  http://localhost:${MOCK_PORT}/health
Next: open n8n and run "A - Usage audit" with the "Run manually" trigger, then see README.md for B, D and C.
The mock vendors fail 5% of calls on purpose. If the first run of A reports a failed fetch, run it once more.
Try the contracts:  scripts/post_contract.sh data/sample-contracts/*.pdf
DONE
