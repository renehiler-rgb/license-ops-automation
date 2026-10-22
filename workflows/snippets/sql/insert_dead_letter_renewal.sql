-- "Insert dead_letter" node of workflow D. Parameters in order: contract_ref, threshold_days, error text.
-- One open row per contract and threshold, so a failing contract does not pile up rows day after day.
INSERT INTO dead_letter (workflow, node, payload, error)
SELECT 'D - Renewal alerts', 'Slack alert',
       jsonb_build_object('contract_ref', $1::text, 'threshold_days', $2::int), $3
WHERE NOT EXISTS (
    SELECT 1 FROM dead_letter
    WHERE workflow = 'D - Renewal alerts' AND status = 'open'
      AND payload->>'contract_ref' = $1::text AND (payload->>'threshold_days')::int = $2::int
);
