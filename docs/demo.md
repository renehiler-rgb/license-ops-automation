# Demo guide

Three ways to see this project, from least to most effort.

## 1. Read it (no setup)

- Screenshots and a short screen recording: `docs/images/` (to be added).
- One page per workflow in `docs/`.
- Workflow JSON in `workflows/`, importable into any n8n instance.

## 2. Run it yourself (recommended)

Follow the Quickstart in the [README](../README.md). Everything runs locally with synthetic data, and nothing connects to the author's machine.

Suggested tour once it is running:

1. Open n8n at <http://localhost:5678> and import the files in `workflows/`.
2. Run the contract expiry workflow manually and inspect each node's output.
3. Query the data directly:
   ```bash
   docker compose exec postgres psql -U licenseops -d licenseops
   ```
4. Check the mock vendor API: `curl -s localhost:8000/health`.
5. Raise `CHAOS_RATE` in `.env` (for example `0.3`), restart the stack, and watch the workflows deal with failing vendor calls.

## 3. Live demo with the author

A live walkthrough is given on a screen share, or on a separate demo instance. **Nobody is given access to the author's machine unless the author explicitly grants it for that session.**

For the author, when granting access is warranted:

- Share only the n8n web UI, and only with the specific person, through Tailscale node sharing or a tailnet invite.
- Postgres, Ollama and the mock API are not part of what is shared.
- Use synthetic data only (it always is).
- Grant access for the session only. Revoke it afterwards in the Tailscale admin console (Machines → Share, or Users).
- Never use public tunnels, Tailscale Funnel, or port forwarding.
