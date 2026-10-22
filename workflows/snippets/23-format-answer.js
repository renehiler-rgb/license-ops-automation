// Code node "Format answer"  (mode: Run Once for All Items)
// Input : the answer of the LLM node (Claude or Ollama), or an error item if the call failed.
// Output: ONE item { http_status, answer, sources, source }.
//   sources = the retrieved passages whose file the answer actually cites (none when the answer is "not in the contracts").

const built = $('Build answer request').first().json;
const source = $('Read question').first().json.source;
const response = $input.first().json;

let answer = null;
if (!response.error) {
  answer = built.provider === 'anthropic'
    ? (response.content ?? []).filter((b) => b.type === 'text').map((b) => b.text).join('\n').trim()
    : String(response.message?.content ?? '').trim();
}

if (!answer) {
  return [{ json: { http_status: 502, source, sources: [],
    answer: 'Sorry, I could not get an answer from the language model right now. Please try again in a moment.' } }];
}

const refused = /that is not in the contracts/i.test(answer);

// A passage counts as cited when the answer names its file (with or without .pdf) and one of the section titles
// it covers. If the answer names a file but no section, the best-matching passage of that file is used.
const mentions = (text) => answer.includes(text);
const seen = new Set();
const sources = [];
if (!refused) {
  const fileNames = [...new Set(built.chunks.map((c) => c.filename))].filter((f) => mentions(f) || mentions(f.replace(/\.pdf$/i, '')));
  for (const file of fileNames) {
    const ofFile = built.chunks.filter((c) => c.filename === file);          // already ordered by similarity
    const bySection = ofFile.filter((c) => c.section.split(' / ').some((title) => answer.includes(title)));
    for (const c of (bySection.length ? bySection : [ofFile[0]])) {
      const key = `${c.filename}|${c.section}`;
      if (!seen.has(key)) { seen.add(key); sources.push(c); }
    }
  }
  // citations of the structured table: [contracts table, NW-CHT-001]
  for (const m of answer.matchAll(/\[contracts table,\s*([A-Z0-9-]+)\]/gi)) {
    const key = `contracts table|${m[1]}`;
    if (!seen.has(key)) { seen.add(key); sources.push({ filename: 'contracts table', section: m[1] }); }
  }
}

return [{ json: { http_status: 200, source, answer, sources } }];
