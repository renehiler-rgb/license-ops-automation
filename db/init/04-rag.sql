-- Contract intake: documents, text chunks and their embeddings.

CREATE TABLE IF NOT EXISTS contract_documents (
    id           serial PRIMARY KEY,
    filename     text NOT NULL,
    sha256       text NOT NULL UNIQUE,           -- same file twice = one row
    received_at  timestamptz NOT NULL DEFAULT now(),
    extracted    jsonb,
    status       text NOT NULL CHECK (status IN ('extracted', 'needs_review', 'failed'))
);

-- Link contracts back to the document they came from (skipped if already there).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'contracts_source_document_fk') THEN
        ALTER TABLE contracts
            ADD CONSTRAINT contracts_source_document_fk
            FOREIGN KEY (source_document_id) REFERENCES contract_documents (id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS contract_chunks (
    id           serial PRIMARY KEY,
    document_id  integer NOT NULL REFERENCES contract_documents (id) ON DELETE CASCADE,
    chunk_index  integer NOT NULL,
    content      text NOT NULL,
    embedding    vector(768),                    -- nomic-embed-text produces 768 numbers
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS contract_chunks_embedding_idx
    ON contract_chunks USING hnsw (embedding vector_cosine_ops);
