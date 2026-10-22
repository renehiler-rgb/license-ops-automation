-- "Log failure" node of workflow C1. Parameters in order: failed (true/false), filename, document_id, error text.
-- Writes a dead_letter row only when the extraction itself failed (for example a wrong API key).
-- One open row per document, so retrying the same file does not pile up rows.
INSERT INTO dead_letter (workflow, node, payload, error)
SELECT 'C1 - Contract intake', 'LLM extraction',
       jsonb_build_object('document_id', $3::int, 'filename', $2::text), $4
WHERE $1::boolean
  AND NOT EXISTS (SELECT 1 FROM dead_letter
                  WHERE workflow = 'C1 - Contract intake' AND node = 'LLM extraction' AND status = 'open'
                    AND (payload->>'document_id')::int = $3::int);
