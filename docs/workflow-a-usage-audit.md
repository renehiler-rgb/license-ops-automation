# Workflow A: Usage & activity audit

Export: `workflows/a-usage-audit.json`. Code and SQL for every node: `workflows/snippets/`
(see its README for node names and query parameters).

## Trigger
Schedule, daily at 06:30 (Europe/Belgrade). It can also be run by hand from the editor.

## Inputs
- **HR directory** (`/hr/employees`, API key, page pagination).
- **Four vendor APIs**, each with a different shape:
  - Chatterly AI and DesignHub: API key, cursor pagination.
  - CodeForge and MeetSpace: OAuth2 client credentials, page pagination.
- **`app_config`** thresholds: `inactive_days`, `new_account_grace_days`, `mismatch_window_days`,
  `mismatch_min_avg_activity`, `usage_initial_days`, `post_empty_digest`, `slack_channel_alerts`.
- **Last sync**: usage is requested only from the last stored day per tool, minus 2 days of overlap.
  The first run pulls `usage_initial_days` (120).

## What it does
1. Load config, start a `workflow_runs` row (shared run log).
2. Fetch HR and all vendor endpoints in parallel. Each fetch retries 4 times, 2000 ms apart.
3. Normalise to one schema (Code nodes). Items with no `external_id` or an unparseable date go to
   `dead_letter` as rejected, not silently dropped.
4. Upsert `employees`, `accounts`, `usage_daily` (all `ON CONFLICT`).
5. Run the audit rules in SQL, shape the findings, upsert `audit_findings`, and resolve findings
   that were not seen in this run.
6. Build one Slack digest of findings that are new (`notified_at is null`), post it, mark them notified.
7. Finish the run log row.

## Audit rules
| Finding | Rule | Severity |
|---|---|---|
| `orphaned_account` | email not in `employees`, or employee terminated | high |
| `inactive_seat` | no activity for more than `inactive_days` (or never, and account older than the grace period) | medium |
| `seat_mismatch` | premium seat with average activity below `mismatch_min_avg_activity` per day | low |
| `duplicate_account` | same person has 2+ accounts in one tool (`+alias` emails) | medium |
| `over_allocation` | accounts in a tool exceed contracted seats | high |

## Outputs
- Tables: `employees`, `accounts`, `usage_daily`, `audit_findings`, `workflow_runs`, `dead_letter`.
- Slack: one digest in `slack_channel_alerts`, grouped by type, top 5 per type.
  If nothing is new, it posts nothing unless `post_empty_digest` is `true`.

## Failure modes
| What goes wrong | What happens |
|---|---|
| Vendor returns 429/500 (chaos) | Retry On Fail, 4 tries. A retry restarts that whole fetch. |
| One vendor stays down | The fetch goes to its error output and into `dead_letter`; the other vendors continue. |
| Bad item (no id, bad date) | Rejected and stored in `dead_letter`. |
| Any uncaught failure | The shared error workflow (`E - Error handler`) posts to Slack and writes `dead_letter`. |
| Re-run | Upserts and the unique finding key mean no duplicates; `last_seen` is refreshed. |

## How to test
1. Generate and load data: `python3 scripts/generate_data.py && python3 scripts/load_data.py`.
2. Run the workflow with `CHAOS_RATE=0`, then `python3 scripts/check_audit.py`.
   It lists planted issues as found, missed or extra.
3. Run it again: no new findings and no new Slack message.
4. Chaos: set `CHAOS_RATE=0.3`, restart `mock-vendors`, run again.
5. Outage: `docker compose stop mock-vendors`, run again, then look at `dead_letter` and Slack.

Setup of the shared blocks (error handler, run log, config loader): [shared-blocks.md](shared-blocks.md).
