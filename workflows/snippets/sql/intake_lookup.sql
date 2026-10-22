-- "Hash and lookup" node of workflow C1. Parameter: the uploaded file as base64.
-- sha256 is computed here in Postgres (Code nodes may not use the crypto module).
-- Returns ONE row: the hash, and the document if this exact file was already stored
-- (status extracted). A document that earlier ended as 'needs_review' or 'failed' is NOT a duplicate:
-- sending it again processes it again, so a fix to the data, the prompt or the model can be applied.
WITH h AS (SELECT encode(sha256(decode($1, 'base64')), 'hex') AS sha256)
SELECT h.sha256, d.id AS document_id, d.status, d.filename, c.contract_ref
FROM h
LEFT JOIN contract_documents d ON d.sha256 = h.sha256 AND d.status = 'extracted'
LEFT JOIN contracts c ON c.source_document_id = d.id
LIMIT 1;
