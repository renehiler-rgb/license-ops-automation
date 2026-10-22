-- "Find due contracts" node of workflow D (Postgres, Execute Query). No parameters.
-- Turn on "Always Output Data" so the workflow still finishes when nothing is due.
--
-- A contract is due when its notice deadline (end date minus notice days) is at most N days away,
-- for a threshold N in app_config.renewal_thresholds (default 90, 60, 30), and that threshold has
-- not been alerted yet. "At most" (not "exactly") means a missed day, for example the machine
-- being off, still gets its alert on the next run instead of never.
-- A contract gets ONE alert per run: the tightest threshold it fits (89 days left -> 90, 59 -> 60).
-- Contracts that already ended are ignored. A deadline already passed shows days_left < 0.
WITH today AS (
    SELECT (now() AT TIME ZONE 'Europe/Belgrade')::date AS day
),
thresholds AS (
    SELECT t::int AS threshold_days
    FROM jsonb_array_elements_text(
             COALESCE((SELECT value FROM app_config WHERE key = 'renewal_thresholds'), '[90, 60, 30]'::jsonb)
         ) AS t
),
contract_days AS (
    SELECT c.id AS contract_id,
           (c.end_date - c.notice_days) - today.day AS days_left
    FROM contracts c, today
    WHERE c.end_date >= today.day
),
picked AS (
    SELECT cd.contract_id, cd.days_left,
           (SELECT min(threshold_days) FROM thresholds WHERE threshold_days >= cd.days_left) AS threshold_days
    FROM contract_days cd
)
SELECT p.contract_id, p.threshold_days, p.days_left, c.contract_ref, t.name AS tool
FROM picked p
JOIN contracts c ON c.id = p.contract_id
JOIN tools t ON t.id = c.tool_id
WHERE p.threshold_days IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM renewal_alerts r
                  WHERE r.contract_id = p.contract_id AND r.threshold_days = p.threshold_days)
ORDER BY p.days_left, c.contract_ref;
