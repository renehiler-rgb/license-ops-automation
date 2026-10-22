# Workflow A snippets: how to wire them in n8n

You build the workflow in the editor; everything that is code or SQL lives here, version-controlled.
Copy a `.js` file into a **Code** node (mode *Run Once for All Items*), and a `.sql` file into a
**Postgres** node (*Execute Query*, credential `licenseops DB`).

## Node names matter
The Code nodes read other nodes by name (`$('Chatterly users')`), so name the nodes **exactly** as below.

```
Schedule 06:30 -> Config -> Run log start -> Last sync -> (fan out)
 |
 +- HR employees ............ -> Normalise employees (01) -> Upsert employees
 +- Chatterly users, Chatterly usage       \
 +- DesignHub users, DesignHub usage        \  (all 8 straight from Last sync, in parallel)
 +- CodeForge members, CodeForge activity   /  -> Merge (Append; only "waits for all") -> Normalise accounts (02)
 +- MeetSpace members, MeetSpace activity  /   -> Upsert accounts -> Normalise usage (03) -> Upsert usage
 -> Audit rules -> Shape findings (04) -> Upsert findings -> Resolve findings
 -> Select new findings -> Build digest (05) -> IF skip=false -> Slack -> Mark notified -> Run log finish
```
Rejected items: after each Normalise node, a Postgres node `insert_rejected.sql` stores `rejected` in `dead_letter`.

## Code nodes
| File | Node name | Output |
|---|---|---|
| `01-normalise-employees.js` | Normalise employees | `{employees, rejected, items_in, items_out}` |
| `02-normalise-accounts.js` | Normalise accounts | `{accounts, rejected, vendors, items_in, items_out}` |
| `03-normalise-usage.js` | Normalise usage | one item per 2000 rows `{usage, rejected, batch, batches, ...}` |
| `04-shape-findings.js` | Shape findings | `{findings, total, by_type}` |
| `05-build-slack-digest.js` | Build digest | `{skip, text, blocks, finding_ids}` |

## SQL files (`sql/`) and their parameters
In the Postgres node open *Options -> Query Parameters* and use an expression.

| File | Node name | Query parameters |
|---|---|---|
| `last_sync.sql` | Last sync | none |
| `upsert_employees.sql` | Upsert employees | `{{ [JSON.stringify($json.employees)] }}` |
| `upsert_accounts.sql` | Upsert accounts | `{{ [JSON.stringify($('Normalise accounts').first().json.accounts)] }}` |
| `upsert_usage.sql` | Upsert usage | `{{ [JSON.stringify($json.usage)] }}` (runs once per batch) |
| `insert_rejected.sql` | Rejected to dead_letter | `{{ [JSON.stringify($json.rejected), 'Normalise accounts'] }}` (use the matching node name) |
| `audit_detect.sql` | Audit rules | none. Turn on *Always Output Data*. |
| `upsert_findings.sql` | Upsert findings | `{{ [JSON.stringify($json.findings)] }}` |
| `resolve_findings.sql` | Resolve findings | `{{ [$('Last sync').first().json.run_started_at] }}` |
| `select_new_findings.sql` | Select new findings | none. Turn on *Always Output Data*. |
| `mark_notified.sql` | Mark notified | `{{ [JSON.stringify($('Build digest').first().json.finding_ids)] }}` |

## HTTP Request nodes (8 vendor nodes + HR)
`workflows/a-usage-audit.json` already contains all nine, configured and tested: import it (or copy the nodes) instead of
building them by hand. It also has the triggers, `Config`, `Last sync` and `Insert dead_letter`.

- **HR employees**: `/hr/employees?page_size=200`, page pagination, complete when `page >= total_pages`.
- **Chatterly users / usage**: cursor pagination, cursor = `$response.body.next_cursor`.
- **DesignHub users / usage**: same, cursor = `$response.body.cursor?.next`.
- **CodeForge / MeetSpace members and activity** (OAuth2): `page` = `{{ $pageCount + 1 }}`, complete when the list is empty.
- Usage `from` / `since` = `{{ $('Last sync').first().json.since.<tool> }}`.
- Every node: Retry On Fail (4 tries, 2000 ms) and On Error -> Continue (using error output) -> `Insert dead_letter`.

Three things that bit during testing (all fixed in the JSON):
1. **Wire every fetch straight from `Last sync`.** If a usage node comes after its users node, it runs once per page the
   users node returned (3 pages = 3 full downloads). Tested: 51 pages instead of 17.
2. **Write the "complete when" expressions with `?.`** (`$response.body.cursor?.next`, `body.members?.length`). On an error
   response the body is `{"detail": ...}`; a plain `body.cursor.next` throws, n8n quietly stops, and the error page is
   returned as if it were data. With `?.` n8n sees the error status and fails the node, so Retry On Fail takes over.
3. **A retry restarts the whole fetch**, not just the failed page. At the normal 5% chaos, daily runs (about 4 pages per
   usage node) are fine. The very first run downloads about 120 days (17-21 pages per usage node); each try succeeds
   about 40% of the time, so if a usage fetch lands in `dead_letter` on the first run, just run it again (upserts make that safe).
   At 30% chaos the large fetches mostly fail, the small ones succeed, and the run still completes.

The Code nodes also protect themselves: a page without the vendor's list counts as a failed vendor (`02`) or a `bad_pages` count (`03`).

Other settings: Slack node: Message Type *Blocks*, Blocks `{{ JSON.stringify({ blocks: $json.blocks }) }}`,
Text `{{ $json.text }}`, channel `{{ $('Config').first().json.cfg.slack_channel_alerts }}`.
The workflow's *Error Workflow* setting is `E - Error handler`.

## Rules (SQL, thresholds in `app_config`)
| Finding | Rule | Severity |
|---|---|---|
| `orphaned_account` | email (lower-case, `+tag` removed) not in `employees`, or employee terminated | high |
| `inactive_seat` | current employee, last active more than `inactive_days` ago (or never, account older than `new_account_grace_days`) | medium |
| `seat_mismatch` | premium seat, average activity per day over `mismatch_window_days` below `mismatch_min_avg_activity` | low |
| `duplicate_account` | same person (after removing `+tag`) has 2+ accounts in one tool; the extra one (normally the alias) is flagged | medium |
| `over_allocation` | accounts in a tool exceed the seats of its contracts in force today | high |

Findings are upserted (`last_seen` refreshed), findings not seen in a run get `resolved_at`,
and one that comes back is re-opened and notified again.

## Checking your work
```
python3 scripts/check_audit.py      # planted issues vs findings: found / missed / extra
```
