// Code node "Read upload"  (mode: Run Once for All Items)
// Input : the Webhook item with the uploaded file as a binary property (multipart/form-data).
// Output: ONE item { ok, problem, filename, size, file_b64 }.
//   file_b64 goes to "Hash and lookup" (the sha256 is computed in Postgres, Code nodes may not use crypto).
//   ok = false means a bad upload (nothing sent, empty, not a PDF, too big): the workflow answers HTTP 400.

const MAX_BYTES = 15 * 1024 * 1024;
const item = $input.first();
// The uploaded file is the first binary property (n8n names it after the form field).
const binaryKey = Object.keys(item.binary ?? {})[0];
const file = binaryKey ? item.binary[binaryKey] : undefined;

let problem = null;
let base64 = null;
let size = 0;

if (!file) {
  problem = 'No file received. Send multipart/form-data with a field named "file".';
} else {
  const buffer = await this.helpers.getBinaryDataBuffer(0, binaryKey);
  size = buffer.length;
  if (size === 0) problem = 'The file is empty.';
  else if (buffer.subarray(0, 5).toString('latin1') !== '%PDF-') problem = 'Only PDF files are accepted.';
  else if (size > MAX_BYTES) problem = 'The file is larger than 15 MB.';
  else base64 = buffer.toString('base64');
}

// Keep only the file name (no folders) and a sane length: it is stored and shown in Slack.
const rawName = String(file?.fileName ?? 'upload.pdf');
const filename = rawName.split(/[\\/]/).pop().slice(0, 200) || 'upload.pdf';

// The file is passed on as the binary property "file" for the "Extract PDF" node.
return [{ json: { ok: problem === null, problem, filename, size, file_b64: base64 }, binary: file ? { file } : {} }];
