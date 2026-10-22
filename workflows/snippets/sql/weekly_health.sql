-- "Health query" node of workflow F (Postgres, Execute Query). No parameters.
-- Returns ONE row, column "health": the last 7 days of workflow_runs and the open dead_letter items.
--   ok       = status success
--   partial  = finished, but a source or step failed (the run still delivered)
--   failed   = status failed, or a run that never finished and is older than 1 hour (it crashed or was stopped)
--   running  = not finished yet and younger than 1 hour (not counted as a failure)
-- success_rate = ok / (runs that are not running). avg_seconds = average over finished runs.
WITH runs AS (
    SELECT workflow, started_at, finished_at,
           CASE
               WHEN status = 'success' THEN 'ok'
               WHEN status = 'partial' THEN 'partial'
               WHEN status = 'failed' OR (finished_at IS NULL AND started_at < now() - interval '1 hour') THEN 'failed'
               WHEN finished_at IS NULL THEN 'running'
               ELSE 'failed'
           END AS outcome
    FROM workflow_runs
    WHERE started_at >= now() - interval '7 days'
),
per_workflow AS (
    SELECT workflow,
           count(*)                                      AS runs,
           count(*) FILTER (WHERE outcome = 'ok')        AS ok,
           count(*) FILTER (WHERE outcome = 'partial')   AS partial,
           count(*) FILTER (WHERE outcome = 'failed')    AS failed,
           count(*) FILTER (WHERE outcome = 'running')   AS running,
           round(100.0 * count(*) FILTER (WHERE outcome = 'ok')
                 / NULLIF(count(*) FILTER (WHERE outcome <> 'running'), 0), 1) AS success_rate,
           round(avg(extract(epoch FROM finished_at - started_at))
                 FILTER (WHERE finished_at IS NOT NULL)::numeric, 1)            AS avg_seconds,
           max(started_at)                                                      AS last_run
    FROM runs
    GROUP BY workflow
),
dead AS (
    SELECT workflow, count(*) AS open_items,
           max(extract(day FROM now() - created_at))::int AS oldest_days
    FROM dead_letter
    WHERE status = 'open'
    GROUP BY workflow
)
SELECT jsonb_build_object(
    'since', to_char(now() - interval '7 days', 'YYYY-MM-DD'),
    'workflows', COALESCE((SELECT jsonb_agg(to_jsonb(p) ORDER BY p.workflow) FROM per_workflow p), '[]'::jsonb),
    'dead_letter_open', COALESCE((SELECT sum(open_items) FROM dead), 0),
    'dead_letter', COALESCE((SELECT jsonb_agg(to_jsonb(d) ORDER BY d.open_items DESC) FROM dead d), '[]'::jsonb)
) AS health;
