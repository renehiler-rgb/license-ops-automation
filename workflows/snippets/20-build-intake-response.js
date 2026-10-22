// Code node "Build response"  (mode: Run Once for All Items)
// Reads the earlier nodes by name and builds the answer for the caller and the facts for the run log.
// Output: { http_status, body: { document_id, status, contract_ref, warnings, errors, indexed }, run_status, note }

const verdict = $('Validate extraction').first().json;
const documentId = $('Store document').first().json.document_id;
const filename = $('Read upload').first().json.filename;

const contractRow = $('Upsert contract').isExecuted ? $('Upsert contract').first().json : {};
const contractRef = contractRow.contract_ref ?? verdict.data?.contract_ref ?? null;

const chunkCount = $('Chunk text').first().json.chunks.length;
const hadChunks = chunkCount > 0;
const savedEmbeddings = $('Save embeddings').isExecuted ? $('Save embeddings').all().length : 0;
// failed when Ollama errored (dead_letter row) or did not return one vector per chunk
const embeddingFailed = hadChunks && ($('Log embedding failure').isExecuted || savedEmbeddings !== chunkCount);
const indexed = hadChunks && !embeddingFailed;

const warnings = [...verdict.warnings];
if (embeddingFailed) warnings.push('embedding_failed: the contract data is stored but not searchable yet (see dead_letter)');
if (!hadChunks && verdict.status !== 'failed') warnings.push('not_indexed: the document was not added to the search index');

// 502 when the extraction itself failed, 200 otherwise (needs_review is a normal outcome, not an error)
const httpStatus = verdict.status === 'failed' ? 502 : 200;
const runStatus = verdict.status === 'failed' ? 'failed'
  : (verdict.status === 'extracted' && !embeddingFailed ? 'success' : 'partial');

return [{
  json: {
    http_status: httpStatus,
    body: { document_id: documentId, status: verdict.status, contract_ref: contractRef, warnings, errors: verdict.errors, indexed },
    run_status: runStatus,
    note: `${filename}: ${verdict.status}${indexed ? ', indexed' : ''}`,
  },
}];
