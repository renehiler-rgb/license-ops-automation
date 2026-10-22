# Shared building blocks

Every workflow in this project uses the same three pieces. Build them once, reuse everywhere.

## 1. Error handler (`workflows/e-error-handler.json`)

`Error Trigger` -> `Config` -> `Build message` -> `Insert dead_letter` -> `Post to Slack`

- The Slack text has the workflow name, failed node, error message and execution link.
- A row goes into `dead_letter` (`status = 'open'`). The insert is skipped if a row with the same
  `payload.execution_id` already exists, so a retry never duplicates it.
- The channel comes from `app_config.slack_channel_alerts`.
- n8n does not give the Error Trigger the failed node's input items, so `payload` holds the execution
  id, URL, mode and stack instead.
- The Slack node has no credential attached in the export. Pick yours after importing.

**For every new workflow:** Workflow Settings -> *Error Workflow* -> `E - Error handler`.

## 2. Run log (`workflows/run-log.json`)

An `Execute Workflow Trigger` sub-workflow. Call it with an *Execute Workflow* node at the start and end of a run.

| field | start | finish |
|---|---|---|
| `action` | `"start"` | `"finish"` |
| `workflow`, `execution_id` | required | required |
| `items_in`, `notes` | optional | optional |
| `items_out`, `status` | - | optional (`status` defaults to `success`) |

Use `{{ $workflow.name }}` and `{{ $execution.id }}` for the two required fields. Both actions
find the row by `workflow` + `execution_id`, so you do not need to carry the row id between calls.
Both return `{id}` (the `workflow_runs` row). Calling `start` twice for the same execution returns the same row.

## 3. Config loader

A Postgres node named **Config**, first in every workflow after the trigger:

```sql
select jsonb_object_agg(key, value) as cfg from app_config;
```

Read values anywhere with `{{ $('Config').first().json.cfg.inactive_days }}`.
Thresholds and feature flags live in `app_config`, never in environment variables.
