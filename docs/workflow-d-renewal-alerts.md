# Workflow D: Renewal alerts

Export: `workflows/d-renewal-alerts.json`. Code and SQL per node: `workflows/snippets/` (`12`, `13`, `sql/renewal_due.sql`, `claim_alert.sql`, `record_alert.sql`, `release_claim.sql`, `insert_dead_letter_renewal.sql`).

## Trigger
Schedule, daily 07:30 (Europe/Belgrade). Can also be run by hand from the editor.

## What it does
1. Load config, start the run log.
2. **Find due contracts (SQL).** The notice deadline is `end_date - notice_days`. A contract is due when the deadline is
   *at most* N days away for a threshold N in `app_config.renewal_thresholds` (default 90, 60, 30) and that threshold was not alerted yet.
   "At most" instead of "exactly" means a missed day (machine off) still produces the alert once, instead of never.
   A contract gets one alert per run, for the tightest threshold it fits (89 days left is the 90-day alert, 59 the 60-day, 29 the 30-day).
   Contracts that already ended are ignored.
3. **Claim the alert** by inserting `(contract_id, threshold_days)` into `renewal_alerts` *before* sending anything.
   The primary key lets only one run succeed, so a second or overlapping run cannot send the same alert twice.
4. **Jira (optional)**, only when `jira_enabled` is `true`: search for an open issue labelled with the contract ref; reuse it if found.
   Create a ticket only if none exists and only at the first (90-day) alert.
5. **Slack alert** to `slack_channel_renewals` (Block Kit: tool, deadline, seats, annual value, owner, ticket).
6. Record the Jira key on the `renewal_alerts` row, finish the run log.

## Why claim first
The old workflow wrote its log at the end, so a failure between sending and logging produced duplicates the next day.
Here the row exists before the Slack post. If Slack fails (after 3 tries) the claim is deleted, a `dead_letter` row is written,
the run is `partial` and the last node fails the execution so the error workflow alerts. The next run retries.

## Failure modes
| What goes wrong | What happens |
|---|---|
| Nothing is due | The run log says "nothing due"; no Slack post. |
| Run twice, or two runs overlap | The second one finds nothing to claim and stops. No duplicate. |
| Slack fails | Claim released, `dead_letter` row, run `partial`, error alert. Retried next run. |
| Jira search fails | No ticket is created (a duplicate is worse than a missing ticket); the Slack alert says so. |
| Jira create fails | The Slack alert is still sent and mentions the missing ticket. |
| Jira ticket exists but the `renewal_alerts` row is lost | The label search finds the open ticket, no second one is created. |

## Config (`app_config`)
`renewal_thresholds`, `slack_channel_renewals`, `jira_enabled`, `jira_base_url`, `jira_project_key`, `jira_issue_type`.

## Jira is optional: how to enable it
1. In n8n create a **Jira Software Cloud** credential (email + API token) and attach it to the two Jira HTTP nodes.
2. Set in `app_config`: `jira_base_url` (for example `https://yourcompany.atlassian.net`), `jira_project_key`, `jira_issue_type`, then `jira_enabled` to `true`:
   ```
   update app_config set value = '"https://yourcompany.atlassian.net"' where key = 'jira_base_url';
   update app_config set value = '"LIC"' where key = 'jira_project_key';
   update app_config set value = 'true' where key = 'jira_enabled';
   ```
With `jira_enabled` false the Jira nodes never run.

## How to test
1. Run D: 3 alerts (the planted contracts at the 90, 60 and 30-day marks). `select * from renewal_alerts;` shows 3 rows.
2. Run D again: "nothing due", no Slack post.
3. Slack failure: set `slack_channel_renewals` to a channel that does not exist and delete one `renewal_alerts` row. The run fails, the row stays deleted, `dead_letter` has an entry. Fix the channel and run again: the alert is sent.
4. Jira (with `jira_enabled` true): the first run creates one ticket, at the 90-day alert. A second run creates none. If you delete that contract's `renewal_alerts` row and run again, the alert is re-sent but the existing ticket is reused, not duplicated.
5. Missed day: insert `(contract_id, 90)` for a contract at 59 days and run: it alerts for 60 once.
