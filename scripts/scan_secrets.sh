#!/usr/bin/env bash
# scan_secrets.sh - look for secrets before committing workflow exports.
#
# Usage:
#   scripts/scan_secrets.sh              # scans workflows/, docs/, scripts/, db/, mock-vendors/
#   scripts/scan_secrets.sh some/path    # scans the paths you give
#
# Exit code 0 = nothing suspicious, 1 = at least one match (printed with file and line).
# Note: exports contain n8n credential ids and names ("credentials": {"id": ...}). Those are
# internal references, not secrets, so they are not flagged.
# A match is only a warning sign: read it, then fix the file or tighten the pattern below.

set -u

# Run from the repo root so the default paths work from anywhere.
cd "$(dirname "$0")/.." || exit 2

if [ "$#" -gt 0 ]; then
  TARGETS=("$@")
else
  TARGETS=(workflows docs scripts db mock-vendors docker-compose.yml README.md .env.example)
fi

# Each line is "label|extended regex".
PATTERNS=(
  "Slack token|xox[abprs]-[A-Za-z0-9-]{10,}"
  "Slack webhook URL|hooks\.slack\.com/services/[A-Za-z0-9/]+"
  "API key (sk-...)|sk-[A-Za-z0-9_-]{16,}"
  "Bearer token|Bearer [A-Za-z0-9._~+/=-]{16,}"
  "AWS access key|AKIA[0-9A-Z]{16}"
  "GitHub token|gh[pousr]_[A-Za-z0-9]{30,}"
  "Private key block|-----BEGIN [A-Z ]*PRIVATE KEY-----"
  "Long base64 string|[A-Za-z0-9+/]{60,}={0,2}"
  "Google Sheet / Drive ID|/d/[A-Za-z0-9_-]{30,}"
  "Credential value in JSON|\"(apiKey|api_key|token|secret|password|clientSecret|accessToken)\"[[:space:]]*:[[:space:]]*\"[^\"]{6,}\""
)

found=0

for entry in "${PATTERNS[@]}"; do
  label="${entry%%|*}"
  regex="${entry#*|}"

  # -I skips binary files (the sample PDFs), -n prints line numbers.
  matches=$(grep -rInE --exclude-dir=__pycache__ --exclude='*.pdf' -- "$regex" "${TARGETS[@]}" 2>/dev/null)

  if [ -n "$matches" ]; then
    # Shorten long lines (workflow JSON can be one huge line) so the output stays readable.
    echo "== $label"
    echo "$matches" | cut -c1-200
    found=1
  fi
done

if [ "$found" -eq 0 ]; then
  echo "scan_secrets: no suspicious strings found."
fi
exit "$found"
