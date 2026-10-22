-- "Last sync" node (Postgres, Execute Query). No parameters.
-- For each tool: the date to ask the vendor for usage from = newest stored day minus 2 days
-- (the overlap is safe because usage upserts are idempotent). First run: usage_initial_days back.
-- Also returns run_started_at, used later to resolve findings that were not seen in this run.
SELECT
    now() AS run_started_at,
    jsonb_object_agg(
        lower(split_part(t.name, ' ', 1)),
        to_char(
            COALESCE(
                (SELECT max(u.day) - 2
                 FROM usage_daily u JOIN accounts a ON a.id = u.account_id
                 WHERE a.tool_id = t.id),
                current_date - COALESCE((SELECT (value #>> '{}')::int FROM app_config
                                         WHERE key = 'usage_initial_days'), 120)
            ),
            'YYYY-MM-DD')
    ) AS since
FROM tools t;
