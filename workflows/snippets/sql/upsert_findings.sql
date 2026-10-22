-- "Upsert findings" node. $1 = findings array from "Shape findings".
-- A finding seen again only gets last_seen/details refreshed. One that had been resolved and
-- comes back is re-opened and will be notified again.
WITH up AS (
    INSERT INTO audit_findings (finding_type, account_id, employee_email, severity, details)
    SELECT f.finding_type, f.account_id, f.employee_email, f.severity, f.details
    FROM jsonb_to_recordset($1::jsonb) AS f(
        finding_type text, account_id int, employee_email text, severity text, details jsonb)
    ON CONFLICT (finding_type, COALESCE(account_id, 0), COALESCE(employee_email, '')) DO UPDATE SET
        last_seen   = now(),
        severity    = EXCLUDED.severity,
        details     = EXCLUDED.details,
        notified_at = CASE WHEN audit_findings.resolved_at IS NOT NULL THEN NULL
                           ELSE audit_findings.notified_at END,
        resolved_at = NULL
    RETURNING (xmax = 0) AS inserted
)
SELECT count(*) FILTER (WHERE inserted)     AS new_findings,
       count(*) FILTER (WHERE NOT inserted) AS seen_again
FROM up;
