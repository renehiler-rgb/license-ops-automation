-- "Release claim" node of workflow D, runs when the Slack post failed after retries.
-- Parameters in order: contract_id, threshold_days. Deleting the claim lets the next run try again.
DELETE FROM renewal_alerts
WHERE contract_id = $1::int AND threshold_days = $2::int
RETURNING contract_id;
