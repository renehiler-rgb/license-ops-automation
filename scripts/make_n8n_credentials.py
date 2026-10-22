"""
make_n8n_credentials.py - write the n8n credentials the workflows need, as a JSON file for `n8n import:credentials`.

  python3 scripts/make_n8n_credentials.py out.json

The values come from .env. The credential IDs and names are fixed: the workflow exports in workflows/ refer to
them, so importing the workflows after these credentials "just works". Credentials whose value is missing are
skipped (Jira and Anthropic are optional; Slack is required and a warning is printed when it is missing).
The file contains secrets: it is written with owner-only permissions and bootstrap.sh deletes it right after the import.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_env import ENV, PLACEHOLDERS, parse  # noqa: E402

MOCK_TOKEN_URL = "http://mock-vendors:8000/oauth/token"


def header_auth(cred_id: str, name: str, header: str, value: str) -> dict:
    """A 'Header Auth' credential: the value is sent in the given HTTP header."""
    return {"id": cred_id, "name": name, "type": "httpHeaderAuth", "data": {"name": header, "value": value}}


def oauth2_client_credentials(cred_id: str, name: str, client_id: str, client_secret: str) -> dict:
    """An 'OAuth2 API' credential using the client-credentials grant against the mock token endpoint."""
    return {
        "id": cred_id, "name": name, "type": "oAuth2Api",
        "data": {
            "grantType": "clientCredentials", "accessTokenUrl": MOCK_TOKEN_URL,
            "clientId": client_id, "clientSecret": client_secret,
            "scope": "", "authQueryParameters": "", "authentication": "header",
            "sendAdditionalBodyProperties": False, "additionalBodyProperties": "",
            "ignoreSSLIssues": False,
        },
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_n8n_credentials.py out.json")
    env = parse(ENV.read_text())
    env.update({k: v for k, v in os.environ.items() if k in env})      # real environment wins

    def has(key: str) -> bool:
        return env.get(key, "") not in PLACEHOLDERS

    credentials = [
        {"id": "AhiED7cuq2sS3DZ6", "name": "licenseops DB", "type": "postgres",
         "data": {"host": "postgres", "port": 5432, "database": "licenseops", "user": "licenseops",
                  "password": env["POSTGRES_PASSWORD"], "maxConnections": 100, "ssl": "disable",
                  "allowUnauthorizedCerts": False, "sshTunnel": False}},
        header_auth("ZRwADNv2vgCL9Cog", "HR API Key", "X-API-Key", env["HR_API_KEY"]),
        header_auth("ch53h48eClkSM6Hh", "Chatterly API Key", "X-API-Key", env["CHATTERLY_API_KEY"]),
        header_auth("KJDrsKEe2g8mXlJP", "DesignHub API Key", "X-API-Key", env["DESIGNHUB_API_KEY"]),
        oauth2_client_credentials("Kbm7NgBCBluOaWn2", "Code Forge", env["CODEFORGE_CLIENT_ID"], env["CODEFORGE_CLIENT_SECRET"]),
        oauth2_client_credentials("Z9HK0GAmZxDC5bvV", "MeetSpace", env["MEETSPACE_CLIENT_ID"], env["MEETSPACE_CLIENT_SECRET"]),
        header_auth("nsb9huAfp5Ah596o", "Intake webhook key", "X-Intake-Key", env["INTAKE_API_KEY"]),
    ]

    # Slack is required (docs/slack-setup.md)
    if has("SLACK_BOT_TOKEN"):
        credentials.append({"id": "8hrTthMYaMAUFbva", "name": "Slack account", "type": "slackApi",
                            "data": {"accessToken": env["SLACK_BOT_TOKEN"]}})
    else:
        print("WARNING: SLACK_BOT_TOKEN is not set, so no Slack credential was created. "
              "The workflows run but every Slack post will fail. See docs/slack-setup.md.", file=sys.stderr)

    # Optional: Jira (renewal tickets) and Anthropic (alternative to the local model)
    if has("JIRA_EMAIL") and has("JIRA_API_TOKEN") and has("JIRA_DOMAIN"):
        credentials.append({"id": "r3ocR5qWUYrvKBx0", "name": "Jira SW Cloud account", "type": "jiraSoftwareCloudApi",
                            "data": {"email": env["JIRA_EMAIL"], "apiToken": env["JIRA_API_TOKEN"], "domain": env["JIRA_DOMAIN"]}})
    if has("ANTHROPIC_API_KEY"):
        credentials.append(header_auth("ANTHROPIC_CRED_ID", "Anthropic API key", "x-api-key", env["ANTHROPIC_API_KEY"]))

    out = Path(sys.argv[1])
    out.write_text(json.dumps(credentials))
    out.chmod(0o600)
    print(f"wrote {len(credentials)} credentials: " + ", ".join(c["name"] for c in credentials))


if __name__ == "__main__":
    main()
