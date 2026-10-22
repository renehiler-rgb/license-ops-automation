-- "Upsert report" node of workflow B. Parameters in order: first day of the month, totals (JSON), summary text.
-- The month is the key, so regenerating a month replaces the row instead of adding another.
INSERT INTO monthly_reports (month, totals, summary)
VALUES ($1::date, $2::jsonb, $3)
ON CONFLICT (month) DO UPDATE SET
    totals     = EXCLUDED.totals,
    summary    = EXCLUDED.summary,
    created_at = now()
RETURNING month, (xmax = 0) AS inserted;
