-- "Hash and lookup" node of workflow C1. Parameter: the uploaded file as base64.
-- sha256 is computed here in Postgres (Code nodes may not use the crypto module).
-- Returns ONE row: the hash, and the document if this exact file was already stored
-- (status extracted or needs_review). A document that earlier ended as 'failed' is NOT a duplicate:
-- sending it again retries it.
WITH h AS (SELECT encode(sha256(decode($1, 'base64')), 'hex') AS sha256)
SELECT h.sha256, d.id AS document_id, d.status, d.filename, c.contract_ref
FROM h
LEFT JOIN contract_documents d ON d.sha256 = h.sha256 AND d.status IN ('extracted', 'needs_review')
LEFT JOIN contracts c ON c.source_document_id = d.id
LIMIT 1;
