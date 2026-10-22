-- "Log embedding failure" node of workflow C1. Parameters in order: document_id, filename, error text.
-- The contract data is already stored; only the search index is missing. The payload is enough to replay it:
-- embed the chunks of this document that still have a NULL embedding.
INSERT INTO dead_letter (workflow, node, payload, error)
SELECT 'C1 - Contract intake', 'Embed chunks',
       jsonb_build_object('document_id', $1::int, 'filename', $2::text), $3
WHERE NOT EXISTS (SELECT 1 FROM dead_letter
                  WHERE workflow = 'C1 - Contract intake' AND node = 'Embed chunks' AND status = 'open'
                    AND (payload->>'document_id')::int = $1::int);
