-- "Save embeddings" node of workflow C1. Parameters in order: document_id, embeddings (JSON array of arrays,
-- in chunk order, as returned by Ollama /api/embed).
UPDATE contract_chunks c
SET embedding = (e.vec)::text::vector
FROM jsonb_array_elements($2::jsonb) WITH ORDINALITY AS e(vec, n)
WHERE c.document_id = $1::int AND c.chunk_index = e.n - 1
RETURNING c.chunk_index;
