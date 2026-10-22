-- "Mark notified" node, runs after the Slack post succeeds. $1 = finding_ids from "Build digest".
UPDATE audit_findings
SET notified_at = now()
WHERE id = ANY (SELECT jsonb_array_elements_text($1::jsonb)::int)
  AND notified_at IS NULL;
