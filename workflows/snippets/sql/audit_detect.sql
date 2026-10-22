-- "Audit rules" node (Postgres, Execute Query). No parameters. Read-only: it only SELECTs.
-- Returns one row per finding: finding_type, account_id, employee_email, severity, details.
-- Thresholds come from app_config (see the cfg CTE).
--
-- Email matching (same rule as the data generator): lower-case, and drop any "+tag"
-- so "ana.nikolic+alias@x" is matched to "ana.nikolic@x". That makes alias accounts
-- duplicates, not orphans.
WITH cfg AS (
    SELECT
        COALESCE((SELECT (value #>> '{}')::int     FROM app_config WHERE key = 'inactive_days'),             30) AS inactive_days,
        COALESCE((SELECT (value #>> '{}')::int     FROM app_config WHERE key = 'new_account_grace_days'),    14) AS grace_days,
        COALESCE((SELECT (value #>> '{}')::int     FROM app_config WHERE key = 'mismatch_window_days'),      30) AS window_days,
        COALESCE((SELECT (value #>> '{}')::numeric FROM app_config WHERE key = 'mismatch_min_avg_activity'),  3) AS min_avg
),

-- Every account with its tool and the employee it belongs to (if any).
acct AS (
    SELECT a.id, a.tool_id, lower(split_part(t.name, ' ', 1)) AS tool_key, t.name AS tool_name,
           t.unit_price_monthly AS price, a.external_id, a.email, a.seat_type,
           a.created_at, a.last_active_at,
           regexp_replace(lower(btrim(a.email)), '\+[^@]*@', '@') AS canon_email,
           e.status AS emp_status
    FROM accounts a
    JOIN tools t ON t.id = a.tool_id
    LEFT JOIN employees e ON e.email = regexp_replace(lower(btrim(a.email)), '\+[^@]*@', '@')
),

-- Orphaned: no matching employee, or the employee has left.
orphaned AS (
    SELECT 'orphaned_account' AS finding_type, id AS account_id, email AS employee_email, 'high' AS severity,
           jsonb_build_object(
               'tool', tool_name, 'external_id', external_id, 'seat_type', seat_type,
               'reason', CASE WHEN emp_status IS NULL THEN 'not_in_hr' ELSE 'terminated' END,
               'last_active_at', last_active_at, 'monthly_cost', price) AS details
    FROM acct
    WHERE emp_status IS NULL OR emp_status = 'terminated'
),

-- Inactive: a current employee whose seat has not been used for inactive_days
-- (or never used, and the account is older than the grace period).
inactive AS (
    SELECT 'inactive_seat', a.id, a.email, 'medium',
           jsonb_build_object(
               'tool', a.tool_name, 'external_id', a.external_id, 'seat_type', a.seat_type,
               'last_active_at', a.last_active_at,
               'days_inactive', CASE WHEN a.last_active_at IS NULL THEN NULL
                                     ELSE (current_date - a.last_active_at::date) END,
               'monthly_cost', a.price)
    FROM acct a, cfg
    WHERE a.emp_status = 'active'
      AND ( a.last_active_at < now() - make_interval(days => cfg.inactive_days)
            OR (a.last_active_at IS NULL AND a.created_at < now() - make_interval(days => cfg.grace_days)) )
),

-- Premium seat with a low daily average over the window. Days with no usage row count as zero.
-- Only judged for tools that have usage data in the window (so a failed usage sync cannot
-- flag every premium seat) and for current employees (leavers are already "orphaned").
usage_window AS (
    SELECT u.account_id,
           sum(u.activity_count)::numeric / cfg.window_days   AS avg_daily,
           count(*) FILTER (WHERE u.activity_count > 0)        AS active_days
    FROM usage_daily u, cfg
    WHERE u.day > current_date - cfg.window_days
    GROUP BY u.account_id, cfg.window_days
),
tools_with_usage AS (
    SELECT DISTINCT a.tool_id
    FROM usage_daily u JOIN accounts a ON a.id = u.account_id, cfg
    WHERE u.day > current_date - cfg.window_days
),
mismatch AS (
    SELECT 'seat_mismatch', a.id, a.email, 'low',
           jsonb_build_object(
               'tool', a.tool_name, 'external_id', a.external_id, 'seat_type', a.seat_type,
               'avg_daily_activity', round(COALESCE(w.avg_daily, 0), 2),
               'active_days', COALESCE(w.active_days, 0),
               'window_days', cfg.window_days, 'monthly_cost', 0)
    FROM acct a
    CROSS JOIN cfg
    LEFT JOIN usage_window w ON w.account_id = a.id
    WHERE a.seat_type = 'premium'
      AND a.emp_status = 'active'
      AND a.tool_id IN (SELECT tool_id FROM tools_with_usage)
      AND COALESCE(w.avg_daily, 0) < cfg.min_avg
),

-- Duplicate: the same person has 2+ accounts in one tool. The account that uses the person's
-- plain email is kept (then the oldest); each extra one, normally the "+alias", gets a finding
-- (account_id = the extra account), so findings stay unique.
ranked AS (
    SELECT acct.*,
           row_number() OVER (PARTITION BY tool_id, canon_email ORDER BY (lower(btrim(email)) <> canon_email), created_at, id) AS rn,
           first_value(external_id) OVER (PARTITION BY tool_id, canon_email ORDER BY (lower(btrim(email)) <> canon_email), created_at, id) AS kept_external_id
    FROM acct
    WHERE emp_status IS NOT NULL
),
duplicate AS (
    SELECT 'duplicate_account', id, canon_email, 'medium',
           jsonb_build_object(
               'tool', tool_name, 'external_id', external_id, 'email', email,
               'duplicate_of', kept_external_id, 'monthly_cost', price)
    FROM ranked
    WHERE rn > 1
),

-- Over-allocation: more accounts than seats in the contracts that are in force today.
-- Not tied to one account, so employee_email carries "tool:<name>" to keep the key unique per tool.
over_allocation AS (
    SELECT 'over_allocation', NULL::int, 'tool:' || ac.tool_key, 'high',
           jsonb_build_object(
               'tool', ac.tool_name, 'accounts', ac.n_accounts, 'seats', COALESCE(s.seats, 0),
               'excess', ac.n_accounts - COALESCE(s.seats, 0),
               'monthly_cost', (ac.n_accounts - COALESCE(s.seats, 0)) * ac.price)
    FROM (SELECT tool_id, tool_key, tool_name, price, count(*) AS n_accounts
          FROM acct GROUP BY tool_id, tool_key, tool_name, price) ac
    LEFT JOIN (SELECT tool_id, sum(seats) AS seats FROM contracts
               WHERE current_date BETWEEN start_date AND end_date GROUP BY tool_id) s
           ON s.tool_id = ac.tool_id
    WHERE ac.n_accounts > COALESCE(s.seats, 0)
)

SELECT * FROM orphaned
UNION ALL SELECT * FROM inactive
UNION ALL SELECT * FROM mismatch
UNION ALL SELECT * FROM duplicate
UNION ALL SELECT * FROM over_allocation;
