-- "Select new findings" node. No parameters. Turn on "Always Output Data" in the node settings,
-- otherwise n8n stops here when there are no new findings and the digest never runs.
SELECT f.id, f.finding_type, f.severity, f.employee_email, f.details,
       (SELECT count(*) FROM accounts) AS accounts_checked
FROM audit_findings f
WHERE f.notified_at IS NULL
  AND f.resolved_at IS NULL
ORDER BY f.finding_type, (f.details->>'monthly_cost')::numeric DESC NULLS LAST, f.id;
