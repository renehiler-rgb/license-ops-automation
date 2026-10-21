-- Reporting views.

-- Per tool: seats bought vs accounts vs accounts active in the last N days.
-- N comes from app_config (inactive_days).
CREATE OR REPLACE VIEW v_seat_utilisation AS
WITH cfg AS (
    SELECT (value #>> '{}')::int AS inactive_days
    FROM app_config
    WHERE key = 'inactive_days'
),
seats AS (
    SELECT tool_id, sum(seats) AS seats_bought
    FROM contracts
    WHERE CURRENT_DATE BETWEEN start_date AND end_date
    GROUP BY tool_id
),
acc AS (
    SELECT a.tool_id,
           count(*) AS accounts,
           count(*) FILTER (
               WHERE a.last_active_at >= now() - make_interval(days => cfg.inactive_days)
           ) AS active_accounts
    FROM accounts a
    CROSS JOIN cfg
    GROUP BY a.tool_id
)
SELECT t.id AS tool_id,
       t.name AS tool,
       COALESCE(s.seats_bought, 0)   AS seats_bought,
       COALESCE(acc.accounts, 0)     AS accounts,
       COALESCE(acc.active_accounts, 0) AS active_accounts
FROM tools t
LEFT JOIN seats s   ON s.tool_id = t.id
LEFT JOIN acc       ON acc.tool_id = t.id;

-- Spend per team, tool and month. Accounts with no matching employee show as 'Unknown'.
CREATE OR REPLACE VIEW v_spend_by_team_month AS
SELECT COALESCE(e.team, 'Unknown')       AS team,
       a.tool_id,
       date_trunc('month', u.day)::date  AS month,
       sum(u.spend_usd)                  AS spend_usd
FROM usage_daily u
JOIN accounts a        ON a.id = u.account_id
LEFT JOIN employees e  ON lower(e.email) = lower(a.email)
GROUP BY COALESCE(e.team, 'Unknown'), a.tool_id, date_trunc('month', u.day)::date;
