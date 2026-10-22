-- "Record alert" node of workflow D, runs after the Slack post worked.
-- Parameters in order: contract_id, threshold_days, jira_key (empty when there is no ticket).
UPDATE renewal_alerts
SET jira_key = COALESCE(NULLIF($3, ''), jira_key),
    sent_at  = now()
WHERE contract_id = $1::int AND threshold_days = $2::int
RETURNING contract_id, threshold_days, jira_key;
