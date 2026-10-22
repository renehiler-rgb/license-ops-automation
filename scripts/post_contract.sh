#!/usr/bin/env bash
# post_contract.sh - send one contract PDF to the intake webhook of workflow C1.
#
# Usage:
#   scripts/post_contract.sh sample-contracts/NW-CHT-001_Chatterly-AI.pdf
#   scripts/post_contract.sh sample-contracts/*.pdf        # several files, one after the other
#
# The key comes from INTAKE_API_KEY in .env (or the environment). N8N_URL defaults to http://localhost:5678.
# The answer is the JSON from the workflow: {document_id, status, contract_ref, warnings[], errors[], indexed}.

set -u
cd "$(dirname "$0")/.." || exit 2

if [ "$#" -eq 0 ]; then
  echo "usage: $0 file.pdf [more.pdf ...]" >&2
  exit 2
fi

# Read the key from .env if it is not already in the environment (a tiny parser, no sourcing of the file).
if [ -z "${INTAKE_API_KEY:-}" ] && [ -f .env ]; then
  INTAKE_API_KEY=$(grep -E '^INTAKE_API_KEY=' .env | head -1 | cut -d= -f2-)
fi
if [ -z "${INTAKE_API_KEY:-}" ]; then
  echo "INTAKE_API_KEY is not set (put it in .env)" >&2
  exit 2
fi

URL="${N8N_URL:-http://localhost:5678}/webhook/contract-intake"
status=0

for file in "$@"; do
  echo "== $file"
  # -F sends multipart/form-data with the field name "file", which is what the webhook expects.
  curl -sS -m 300 -X POST "$URL" -H "X-Intake-Key: $INTAKE_API_KEY" -F "file=@$file" -w '\n[HTTP %{http_code}]\n' || status=1
done
exit "$status"
