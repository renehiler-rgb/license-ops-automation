-- "Save chunks" node of workflow C1. Parameters in order: document_id, chunks (JSON array of {chunk_index, content}).
-- The text is saved first, the embeddings follow in the next step. If embedding fails, the chunks stay with a
-- NULL embedding and can be embedded later (see embed_missing in docs). Chunks that no longer exist after a
-- re-ingest are removed.
WITH up AS (
    INSERT INTO contract_chunks (document_id, chunk_index, content, embedding)
    SELECT $1::int, (c->>'chunk_index')::int, c->>'content', NULL
    FROM jsonb_array_elements($2::jsonb) AS c
    ON CONFLICT (document_id, chunk_index) DO UPDATE SET content = EXCLUDED.content, embedding = NULL
    RETURNING 1
),
gone AS (
    DELETE FROM contract_chunks
    WHERE document_id = $1::int
      AND chunk_index >= jsonb_array_length($2::jsonb)
    RETURNING 1
)
SELECT (SELECT count(*) FROM up) AS saved, (SELECT count(*) FROM gone) AS removed;
