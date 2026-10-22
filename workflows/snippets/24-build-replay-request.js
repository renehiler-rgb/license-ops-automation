// Code node "Build replay request"  (mode: Run Once for Each Item)
// Input : one open dead_letter row with the chunks that still need an embedding.
// Output: { dead_letter_id, document_id, indexes, has_chunks, embed_request }.
// A document with nothing left to embed (someone fixed it by hand) is just closed.

const row = $json;
const chunks = row.chunks ?? [];
const cfg = $('Config').first().json.cfg;

return {
  json: {
    dead_letter_id: row.dead_letter_id,
    document_id: row.document_id,
    has_chunks: chunks.length > 0,
    indexes: chunks.map((c) => c.chunk_index),
    embed_request: {
      model: cfg.ollama_embed_model ?? 'nomic-embed-text',
      input: chunks.map((c) => `search_document: ${c.content}`),
    },
  },
};
