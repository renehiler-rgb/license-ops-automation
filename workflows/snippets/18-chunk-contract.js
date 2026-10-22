// Code node "Chunk text"  (mode: Run Once for All Items)
// Input : any item (the data comes from earlier nodes by name).
// Output: ONE item { document_id, chunks: [{ chunk_index, content }], embed_request }.
//   chunks is empty for anything that is not a readable contract (an invoice, a scan, a failed extraction),
//   so those are not added to the search index.
// Chunks are about 800 characters with 150 characters of overlap. Each one starts with the section
// title(s) it covers, so an answer can cite "[file, section]".

const TARGET = 800;
const OVERLAP = 150;
const MIN_SECTION = 250;          // a section smaller than this is merged into the next chunk

const verdict = $('Validate extraction').first().json;
const documentId = $('Store document').first().json.document_id;
const filename = $('Read upload').first().json.filename;
const cfg = $('Config').first().json.cfg;
const text = String($('Extract PDF').first().json.text ?? '');

const isContract = verdict.extracted?.data?.document_type === 'contract' && verdict.status !== 'failed';
if (!isContract || text.trim().length === 0) {
  return [{ json: { document_id: documentId, filename, chunks: [], embed_request: null } }];
}

// A heading is a short line without final punctuation: "4. Renewal and notice", "Your data", "Schedule 1 - Order".
function isHeading(line) {
  const t = line.trim();
  if (t.length < 3 || t.length > 60) return false;
  if (/[.,;:]$/.test(t)) return false;
  if (/^\d+\.\s+\S/.test(t)) return true;
  return /^[A-Z][A-Za-z0-9 ,&\-\/]+$/.test(t) && t.split(' ').length <= 6;
}

const chunks = [];
let heading = 'Document';
let buffer = '';
let sections = [];

function flush() {
  const body = buffer.trim();
  if (!body) return;
  const label = [...new Set(sections.length ? sections : [heading])].slice(0, 3).join(' / ');
  chunks.push({ chunk_index: chunks.length, content: `Section: ${label}\n${body}` });
  // keep the end of this chunk as the start of the next one (cut at a word boundary)
  const tail = body.slice(-OVERLAP);
  buffer = tail.includes(' ') ? tail.slice(tail.indexOf(' ') + 1) : tail;
  sections = [heading];
}

for (const rawLine of text.split(/\r?\n/)) {
  const line = rawLine.trim();
  if (!line) continue;
  if (isHeading(line)) {
    if (buffer.length >= MIN_SECTION + OVERLAP) flush();        // close the previous section if it is big enough
    heading = line;
    sections.push(line);
    continue;
  }
  if (sections.length === 0) sections.push(heading);
  buffer += (buffer ? ' ' : '') + line;
  if (buffer.length >= TARGET) flush();
}
if (buffer.trim().length > OVERLAP || chunks.length === 0) flush();

const embedModel = cfg.ollama_embed_model ?? 'nomic-embed-text';
const embedRequest = { model: embedModel, input: chunks.map((c) => `search_document: ${c.content}`) };

return [{ json: { document_id: documentId, filename, chunks, embed_request: embedRequest } }];
