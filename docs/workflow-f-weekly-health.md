# Workflow F: Weekly health summary

Export: `workflows/f-weekly-health.json`. Code and SQL: `workflows/snippets/14-build-health-report.js`, `workflows/snippets/sql/weekly_health.sql`.

## Trigger
Schedule, Mondays 09:00 (Europe/Belgrade). Can also be run by hand from the editor.

## What it does
1. Load config, start the run log (F logs itself like every workflow).
2. **Health query (SQL):** from `workflow_runs` for the last 7 days, per workflow: runs, ok / partial / failed / running,
   success rate and average duration. From `dead_letter`: open items per workflow and how old the oldest is.
3. **Build health report (Code):** one Slack message, one line per workflow with a green, yellow or red dot.
4. Post to `slack_channel_alerts` and finish the run log.

## How runs are counted
- `ok` = status `success`. `partial` = the run finished but a source or step failed (for example one vendor was down).
- `failed` = status `failed`, or a run that never finished and started more than an hour ago (it crashed or was stopped).
- `running` = not finished and younger than an hour; it is not counted as a failure.
- Success rate = ok / runs that are not running. Average duration is over finished runs.
- A workflow with no runs in the week does not appear. If nothing ran at all the message says so, which usually means the schedules are not published.

## Failure modes
| What goes wrong | What happens |
|---|---|
| Slack fails | Retried 3 times, then the error workflow alerts. |
| Database unreachable | The run fails and the error workflow alerts. |

## How to test
Run F from the editor and read the post in the alerts channel. Check the numbers against
`select workflow, status, count(*) from workflow_runs where started_at > now() - interval '7 days' group by 1, 2;`.
