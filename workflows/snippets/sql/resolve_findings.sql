-- "Resolve findings" node. $1 = run_started_at (from the "Last sync" node).
-- Anything still open that this run did not touch is gone: mark it resolved (history is kept).
UPDATE audit_findings
SET resolved_at = now()
WHERE resolved_at IS NULL
  AND last_seen < $1::timestamptz
RETURNING id;
