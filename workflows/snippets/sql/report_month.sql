-- "Compute report" node (Postgres, Execute Query) of workflow B.
-- $1 = first day of the reporting month, e.g. '2026-09-01'.
-- Returns ONE row, column "report": { month, by_tool: [...], by_team_tool: [...] }.
-- by_tool has one row per tool with budget, variance, cost per active user, idle cost and the
-- change against the previous month. by_team_tool is the per-team breakdown (also used for the CSV).
WITH tool_month AS (
    -- all months, so the previous month is available for the comparison
    SELECT tool_id, tool, month,
           sum(committed)    AS committed,
           sum(usage_spend)  AS usage_spend,
           sum(actual)       AS actual,
           sum(budget)       AS budget,
           sum(accounts)     AS accounts,
           sum(active_users) AS active_users,
           sum(idle_cost)    AS idle_cost
    FROM v_budget_variance
    GROUP BY tool_id, tool, month
),
tool_report AS (
    SELECT t.*,
           lag(t.actual) OVER (PARTITION BY t.tool_id ORDER BY t.month) AS prev_actual
    FROM tool_month t
),
by_tool AS (
    SELECT jsonb_agg(jsonb_build_object(
               'tool', tool,
               'committed', round(committed, 2),
               'usage_spend', round(usage_spend, 2),
               'actual', round(actual, 2),
               'budget', round(budget, 2),
               'variance', round(actual - budget, 2),
               'variance_pct', round(100 * (actual - budget) / NULLIF(budget, 0), 1),
               'accounts', accounts,
               'active_users', active_users,
               'cost_per_active_user', round(actual / NULLIF(active_users, 0), 2),
               'idle_cost', round(idle_cost, 2),
               'prev_actual', round(prev_actual, 2),
               'mom_change', round(actual - prev_actual, 2),
               'mom_pct', round(100 * (actual - prev_actual) / NULLIF(prev_actual, 0), 1)
           ) ORDER BY tool) AS rows
    FROM tool_report
    WHERE month = $1::date
),
by_team_tool AS (
    SELECT jsonb_agg(jsonb_build_object(
               'team', team, 'tool', tool,
               'actual', actual, 'budget', budget,
               'variance', variance, 'variance_pct', variance_pct,
               'accounts', accounts, 'active_users', active_users,
               'cost_per_active_user', cost_per_active_user,
               'idle_cost', idle_cost
           ) ORDER BY team, tool) AS rows
    FROM v_budget_variance
    WHERE month = $1::date
)
SELECT jsonb_build_object(
           'month', to_char($1::date, 'YYYY-MM'),
           'by_tool', COALESCE((SELECT rows FROM by_tool), '[]'::jsonb),
           'by_team_tool', COALESCE((SELECT rows FROM by_team_tool), '[]'::jsonb)
       ) AS report;
