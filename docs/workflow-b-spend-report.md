# Workflow B: Monthly spend & finance report

Export: `workflows/b-spend-report.json`. Code and SQL per node: `workflows/snippets/` (files `06`-`11`, `sql/report_month.sql`, `sql/upsert_report.sql`).
Views: `db/init/06-finance-views.sql`. Number check: `scripts/check_spend.py`.

## Trigger
- **Schedule:** 1st of the month, 08:30 (Europe/Belgrade). Reports the previous month.
- **Webhook:** `POST /webhook/spend-report` with `{"month": "2026-09"}`. Regenerates any past or current month.
  An empty body means the previous month. A bad or future month returns HTTP 400.
- **Manual:** run from the editor (previous month).

```
curl -X POST localhost:5678/webhook/spend-report -H 'Content-Type: application/json' -d '{"month":"2026-09"}'
```

## What it does
1. Resolve and validate the month, load config, start the run log.
2. **Compute (SQL):** one query on the views `v_monthly_spend` and `v_budget_variance`: per tool and per team + tool, actual vs budget, variance, active users, cost per active user, idle cost, change vs the previous month.
3. **Shape (Code):** overall totals, teams over budget, top 3 variances, top 3 idle-cost tools, biggest month-over-month movers.
4. **Summary (local model):** the aggregated numbers (tool and team names with money, no people, no emails) go to Ollama
   (`ollama_summary_model`, default `llama3.1:8b`) with a JSON schema `{headline, three_points[3], recommended_action}`.
   The answer is validated in a Code node. If it is unusable the call is repeated once; if that fails too, a template builds the summary.
   A bad or missing model never blocks the report.
5. **Deliver:** upsert into `monthly_reports` (the month is the key, so regenerating replaces the row), post to Slack
   (`slack_channel_reports`) with Block Kit, then upload a per-team CSV into the thread (optional, see below).
6. Finish the run log: `success`, or `partial` when the template summary was used.

## How cost is counted
- `committed` = contract seats x price per seat, prorated by the days the contract is in force that month.
  Annual and monthly billing cost the same per month (accrual basis); the billing cycle only changes when cash leaves.
- `actual` = `committed` + metered usage spend (only Chatterly AI has usage spend).
  The spec's "usage only for Chatterly" would ignore its seat contract, and the budgets are built from seats plus usage, so both are counted.
- A contract belongs to a tool, not a team: committed cost is shared between teams by their account count that month.
  Accounts with no matching employee are team `Unknown` (no budget).
- `idle_cost` = accounts with no activity in the month x list price of one seat. Months with partial usage data (the first and the current one) overstate it.
- `variance` > 0 means over budget.

## Config (`app_config`)
`slack_channel_reports`, `ollama_url`, `ollama_summary_model`.

## Failure modes
| What goes wrong | What happens |
|---|---|
| Ollama down or slow (60 s timeout) | One retry, then the template summary. Report still stored and posted, run log `partial`. |
| Ollama answers with bad JSON | Same: retry once, then template. |
| Month has no data | `Shape report` fails, the error workflow alerts Slack. |
| Slack post fails | Retried 3 times; the report row is already stored. The error workflow alerts. |
| CSV upload fails | Ignored on purpose (the Slack bot needs the `files:write` scope). The report is unaffected. |
| Same month run twice | `monthly_reports` row is replaced, not duplicated. Slack gets a second post (it is a regeneration). |

## How to test
1. For each of 2026-07, 2026-08, 2026-09, call the webhook; check three `monthly_reports` rows, then `python3 scripts/check_spend.py`.
2. Call the same month again: still one row per month, `created_at` newer.
3. Set `ollama_url` in `app_config` to a dead address and call again: `summary_source` is `template` and the report is still posted. Set it back afterwards.
