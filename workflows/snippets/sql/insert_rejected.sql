-- "Rejected to dead_letter" node. $1 = rejected array, $2 = Code node name (e.g. 'Normalise accounts').
-- Same rejected item twice (while still open) is stored once, so re-runs do not pile up.
INSERT INTO dead_letter (workflow, node, payload, error)
SELECT 'A - Usage audit', $2, r.item, r.reason
FROM jsonb_to_recordset($1::jsonb) AS r(item jsonb, reason text)
WHERE NOT EXISTS (
    SELECT 1 FROM dead_letter d
    WHERE d.workflow = 'A - Usage audit' AND d.node = $2
      AND d.payload = r.item AND d.status = 'open'
);
