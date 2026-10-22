-- Finance views for workflow B (monthly spend report).
--
-- How cost is counted (accrual basis, per month):
--   committed    = contract seats x price per seat, prorated by the days the contract is in force
--                  in that month. Annual and monthly billing cost the same per month here; the
--                  billing cycle only changes when cash leaves, not what a month costs.
--   usage_spend  = metered spend from usage_daily (only Chatterly AI has any).
--   actual       = committed + usage_spend.
-- A contract belongs to a tool, not a team, so a tool's committed cost is shared between the
-- teams in proportion to how many accounts each team had that month.
-- Accounts that match no employee are reported as team 'Unknown'.

-- One row per tool, team and month.
CREATE OR REPLACE VIEW v_monthly_spend AS
WITH months AS (
    SELECT DISTINCT date_trunc('month', day)::date AS month FROM usage_daily
    UNION
    SELECT DISTINCT month FROM budgets
),

-- Contract cost per tool and month, prorated by days in force.
committed AS (
    SELECT c.tool_id, m.month,
           sum(c.seats * c.price_per_seat
               * (least(c.end_date, (m.month + interval '1 month')::date - 1)
                  - greatest(c.start_date, m.month) + 1)
               / ((m.month + interval '1 month')::date - m.month)::numeric) AS committed
    FROM months m
    JOIN contracts c
      ON c.start_date < (m.month + interval '1 month')::date
     AND c.end_date  >= m.month
    GROUP BY c.tool_id, m.month
),

-- Every account with its team; the "+tag" of an alias address is ignored when matching.
acct AS (
    SELECT a.id, a.tool_id, a.created_at,
           COALESCE(e.team, 'Unknown') AS team
    FROM accounts a
    LEFT JOIN employees e
           ON lower(e.email) = regexp_replace(lower(a.email), '\+[^@]*@', '@')
),

-- Accounts that existed during each month.
team_accounts AS (
    SELECT a.tool_id, a.team, m.month, count(*) AS accounts
    FROM acct a
    JOIN months m ON a.created_at < (m.month + interval '1 month')
    GROUP BY a.tool_id, a.team, m.month
),

-- Accounts with any activity in the month.
active AS (
    SELECT a.tool_id, a.team, date_trunc('month', u.day)::date AS month,
           count(DISTINCT a.id) AS active_users
    FROM usage_daily u
    JOIN acct a ON a.id = u.account_id
    WHERE u.activity_count > 0
    GROUP BY a.tool_id, a.team, date_trunc('month', u.day)::date
)

SELECT ta.tool_id,
       t.name AS tool,
       ta.team,
       ta.month,
       ta.accounts,
       COALESCE(ac.active_users, 0) AS active_users,
       round(COALESCE(c.committed, 0) * ta.accounts
             / sum(ta.accounts) OVER (PARTITION BY ta.tool_id, ta.month), 2)  AS committed,
       round(COALESCE(sp.spend_usd, 0), 2)                                    AS usage_spend,
       round(COALESCE(c.committed, 0) * ta.accounts
             / sum(ta.accounts) OVER (PARTITION BY ta.tool_id, ta.month)
             + COALESCE(sp.spend_usd, 0), 2)                                  AS actual,
       -- accounts nobody touched in the month, at the list price of one seat
       greatest(ta.accounts - COALESCE(ac.active_users, 0), 0)                AS idle_accounts,
       round(greatest(ta.accounts - COALESCE(ac.active_users, 0), 0)
             * t.unit_price_monthly, 2)                                       AS idle_cost
FROM team_accounts ta
JOIN tools t ON t.id = ta.tool_id
LEFT JOIN committed c  ON c.tool_id = ta.tool_id AND c.month = ta.month
LEFT JOIN active ac    ON ac.tool_id = ta.tool_id AND ac.team = ta.team AND ac.month = ta.month
LEFT JOIN v_spend_by_team_month sp
       ON sp.tool_id = ta.tool_id AND sp.team = ta.team AND sp.month = ta.month;

-- The same rows with the budget, the variance and the change against the previous month.
-- variance > 0 means over budget.
CREATE OR REPLACE VIEW v_budget_variance AS
SELECT s.tool_id, s.tool, s.team, s.month,
       s.committed, s.usage_spend, s.actual,
       b.amount                                                    AS budget,
       round(s.actual - b.amount, 2)                               AS variance,
       round(100 * (s.actual - b.amount) / NULLIF(b.amount, 0), 1) AS variance_pct,
       s.accounts, s.active_users,
       round(s.actual / NULLIF(s.active_users, 0), 2)              AS cost_per_active_user,
       s.idle_accounts, s.idle_cost,
       lag(s.actual) OVER (PARTITION BY s.tool_id, s.team ORDER BY s.month)             AS prev_actual,
       round(s.actual - lag(s.actual) OVER (PARTITION BY s.tool_id, s.team ORDER BY s.month), 2) AS mom_change
FROM v_monthly_spend s
LEFT JOIN budgets b
       ON b.tool_id = s.tool_id AND b.team = s.team AND b.month = s.month;
