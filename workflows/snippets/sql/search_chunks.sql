-- "Search chunks" node of workflow C2. Parameter: the question embedding as text, e.g. '[0.12,-0.03,...]' (empty = no search).
-- The 6 chunks closest to the question by cosine distance (<=>), with the file and contract they belong to.
-- similarity = 1 - distance (1 means identical direction). Chunks without an embedding are ignored.
SELECT d.filename,
       c.chunk_index,
       split_part(split_part(c.content, E'\n', 1), 'Section: ', 2) AS section,
       c.content,
       ct.contract_ref,
       round((1 - (c.embedding <=> NULLIF($1, '')::vector))::numeric, 3) AS similarity
FROM contract_chunks c
JOIN contract_documents d ON d.id = c.document_id
LEFT JOIN contracts ct ON ct.source_document_id = d.id
WHERE NULLIF($1, '') IS NOT NULL
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> NULLIF($1, '')::vector
LIMIT 6;
