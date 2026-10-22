-- "Open embedding failures" node of the replay workflow. No parameters. Turn on "Always Output Data".
-- One row per open dead_letter entry of workflow C1 whose step was "Embed chunks", with the chunks of that
-- document that still have no embedding (the text was saved, only the search index is missing).
SELECT dl.id AS dead_letter_id,
       (dl.payload->>'document_id')::int AS document_id,
       (SELECT jsonb_agg(jsonb_build_object('chunk_index', c.chunk_index, 'content', c.content) ORDER BY c.chunk_index)
        FROM contract_chunks c
        WHERE c.document_id = (dl.payload->>'document_id')::int AND c.embedding IS NULL) AS chunks
FROM dead_letter dl
WHERE dl.workflow = 'C1 - Contract intake' AND dl.node = 'Embed chunks' AND dl.status = 'open'
ORDER BY dl.id;
