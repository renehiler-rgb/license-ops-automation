-- "Store document" node of workflow C1. Parameters in order: filename, sha256, status, extracted (JSON).
-- The hash is unique, so posting the same file again updates this row instead of adding another.
INSERT INTO contract_documents (filename, sha256, status, extracted)
VALUES ($1, $2, $3, $4::jsonb)
ON CONFLICT (sha256) DO UPDATE SET
    filename    = EXCLUDED.filename,
    status      = EXCLUDED.status,
    extracted   = EXCLUDED.extracted,
    received_at = now()
RETURNING id AS document_id, status;
