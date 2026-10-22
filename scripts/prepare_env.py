"""
prepare_env.py - make sure .env exists and has a value for every secret.

  python3 scripts/prepare_env.py

What it does:
  1. Copies .env.example to .env if there is no .env yet.
  2. Replaces every placeholder ("change-me" or an empty value) with a random secret,
     EXCEPT the values only you can supply (SLACK_BOT_TOKEN, the optional Jira and Anthropic keys).
  3. Never changes a value that already looks real, so it is safe to run again.

The mock vendor keys, the Postgres password, the n8n encryption key and the intake key are all made up by
this project, so random values are exactly right. Nothing here is printed except the names of the keys it filled.
"""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

# Values that only the user can provide: never generated.
USER_SUPPLIED = {"SLACK_BOT_TOKEN", "ANTHROPIC_API_KEY", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_DOMAIN"}
PLACEHOLDERS = {"", "change-me", "replace-with-existing-key"}


def make_secret(key: str) -> str:
    """A random secret. The n8n owner password must contain a capital letter and a digit, so it gets both."""
    if key == "N8N_OWNER_PASSWORD":
        return secrets.token_urlsafe(14) + "Aa1"
    return secrets.token_hex(24)


def parse(text: str) -> dict[str, str]:
    """Read KEY=value lines (comments and blank lines are ignored)."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    if not ENV.exists():
        ENV.write_text(EXAMPLE.read_text())
        print("created .env from .env.example")

    lines = ENV.read_text().splitlines()
    current = parse(ENV.read_text())
    filled = []
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            key, value = key.strip(), value.strip()
            if key not in USER_SUPPLIED and value in PLACEHOLDERS:
                line = f"{key}={make_secret(key)}"
                filled.append(key)
        new_lines.append(line)

    # keys that exist in .env.example but are missing from .env (an older .env): add them
    example = parse(EXAMPLE.read_text())
    for key, value in example.items():
        if key not in current and key not in {k for k in filled}:
            if key in USER_SUPPLIED or value not in PLACEHOLDERS:
                new_lines.append(f"{key}={value if value not in PLACEHOLDERS else ''}")
            else:
                new_lines.append(f"{key}={make_secret(key)}")
                filled.append(key)

    ENV.write_text("\n".join(new_lines) + "\n")
    ENV.chmod(0o600)                       # the file holds secrets: owner only
    if filled:
        print("generated random values for: " + ", ".join(filled))
    else:
        print(".env already complete")

    missing = [k for k in ("SLACK_BOT_TOKEN",) if parse(ENV.read_text()).get(k, "") in PLACEHOLDERS]
    if missing:
        print("STILL NEEDED from you: " + ", ".join(missing) + "  (see docs/slack-setup.md)")


if __name__ == "__main__":
    main()
