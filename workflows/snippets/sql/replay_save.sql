-- "Save replayed embeddings" node of the replay workflow.
-- Parameters in order: document_id, embeddings (JSON array of vectors), chunk indexes (JSON array, same order).
-- Returns ONE row (the number of chunks saved) so the next node runs once per dead_letter entry.
WITH up AS (
    UPDATE contract_chunks c
    SET embedding = (e.vec)::text::vector
    FROM jsonb_array_elements($2::jsonb) WITH ORDINALITY AS e(vec, n)
    JOIN jsonb_array_elements_text($3::jsonb) WITH ORDINALITY AS i(chunk_index, m) ON m = n
    WHERE c.document_id = $1::int AND c.chunk_index = i.chunk_index::int
    RETURNING c.chunk_index
)
SELECT count(*) AS saved FROM up;
