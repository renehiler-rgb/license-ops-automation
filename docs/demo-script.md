# Demo script (live demo, GIF and screenshots)

A 4-minute story for a client or a recording. Each scene says what to run, what to show, and the one sentence that matters.
Before you start: stack running, Slack open on the three channels side by side, n8n open, a terminal in the repo. For a clean recording
run `CHAOS_RATE=0` (default) and use a fresh copy of the data (`scripts/bootstrap.sh`).

| # | Scene (about) | Do | Show | Say |
|---|---|---|---|---|
| 1 | The problem (20 s) | nothing | the README title | "SaaS seats go unused, contracts renew by surprise, and nobody can ask what a contract says." |
| 2 | Audit (40 s) | in n8n open **A - Usage audit**, click *Execute workflow* | the canvas running; then the Slack digest in `#automation-alerts` | "Four vendors with four different APIs and an HR directory, normalised into one schema. 42 findings, about $600 a month." |
| 3 | Proof (15 s) | `.venv/bin/python scripts/check_audit.py` | "every planted issue was found, nothing extra" | "The data has hidden problems, so I can prove what the audit finds and misses." |
| 4 | Spend report (40 s) | `curl` the report webhook (README step 5) | the report in `#license-reports` with the CSV in its thread | "Actual against budget per team, written by a local model that only sees aggregated numbers." |
| 5 | Contracts (60 s) | `scripts/post_contract.sh data/sample-contracts/*.pdf`; then the chat page or the `ask-contracts` curl: "Which contracts auto-renew?", "What is our policy on parental leave?" | answers with sources; the refusal; the invoice in `needs_review` with its reasons | "It answers only from the contracts, cites where, and says so when the answer is not there." |
| 6 | Renewals (20 s) | run **D - Renewal alerts** | three alerts in Slack; run again: nothing | "Once each, even if I run it twice." |
| 7 | Failure (40 s) | set `CHAOS_RATE=0.5` in `.env`, `docker compose up -d mock-vendors`, run A again | the digest naming the failed vendors, the red alert, `select * from dead_letter` | "Two vendors went down. The run finished, said which ones, and nothing was lost." |

## Screenshots to take (`docs/images/`)
1. `canvas-a.png`, `canvas-b.png`, `canvas-c1.png`, `canvas-c2.png`, `canvas-d.png`: each workflow canvas, zoomed to fit. Tidy first: consistent node names, a sticky note per section.
2. `slack-digest.png`, `slack-report.png` (with the CSV), `slack-renewal.png`, `slack-review.png` (the invoice), `slack-health.png`.
3. `chat-answer.png`: a question with its sources, and `chat-refusal.png`.
4. `slack-failure.png`: the error alert; `dead-letter.png`: the table in psql.

## Recording the GIF
Ubuntu: Peek or Kooha; or record on a Mac. Aim for 30 to 45 seconds: scenes 2, 4, 5 and 7, cut tight, 1000 px wide. Put it at the marked spot in the README and attach it to the release.

## If something fails during the demo
Slack silent: check the token and channel (`docs/slack-setup.md`). Model slow: the first question after a pause loads the model (about a minute with a 32B model), so ask one question before you start. Anything else: `docker compose logs -f n8n`.
