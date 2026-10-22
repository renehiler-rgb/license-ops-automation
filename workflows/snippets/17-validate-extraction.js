// Code node "Validate extraction"  (mode: Run Once for All Items)
// Input : the answer of the LLM node (Claude or Ollama), or the "Build extraction request" item when the PDF had no text.
// Output: ONE item { status, valid, llm_failed, errors, warnings, data, extracted }.
//   status  = 'extracted' (all checks passed), 'needs_review' (a check failed: a person must look) or 'failed' (the LLM call failed)
//   errors  = named reasons that block the automatic upsert; warnings = things worth knowing
//   extracted = what is stored in contract_documents.extracted
// Nothing here ever throws on bad model output: a bad answer becomes needs_review, never a crash.

const built = $('Build extraction request').first().json;
const ref = $('Load reference data').first().json;
const knownTools = (ref.tools ?? []).map((t) => String(t).toLowerCase());
const existingByRef = Object.fromEntries((ref.contracts ?? []).map((c) => [c.contract_ref, c]));
const answer = $input.first().json;

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CHF', 'RSD'];
const errors = [];
const warnings = [];

// ---- 1. get the model's data out of the response ----
let data = null;
let llmFailed = false;
let failReason = null;

if (!built.text_ok) {
  errors.push('no_text: the PDF has no readable text (a scan?)');
} else if (answer.error) {
  llmFailed = true;
  failReason = `LLM call failed: ${answer.error.message ?? answer.error}`;
} else if (built.provider === 'anthropic') {
  const block = (answer.content ?? []).find((b) => b.type === 'tool_use');
  if (block?.input) data = block.input;
  else { llmFailed = true; failReason = `Claude returned no tool call (stop_reason ${answer.stop_reason ?? 'unknown'})`; }
} else {
  try { data = JSON.parse(answer.message?.content ?? ''); }
  catch (e) { llmFailed = true; failReason = 'Ollama answer is not valid JSON'; }
}
if (llmFailed) errors.push(failReason);

// ---- 2. check the data ----
const isDate = (s) => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s));

if (data) {
  if (data.document_type !== 'contract') errors.push(`not_a_contract: the document looks like "${data.document_type}"`);

  for (const field of ['vendor', 'product', 'contract_ref', 'start_date', 'end_date', 'seats',
    'price_per_seat', 'currency', 'billing_cycle', 'auto_renew', 'notice_days']) {
    if (data[field] === null || data[field] === undefined || data[field] === '') errors.push(`missing_field: ${field}`);
  }

  if (data.start_date && !isDate(data.start_date)) errors.push(`bad_date: start_date "${data.start_date}"`);
  if (data.end_date && !isDate(data.end_date)) errors.push(`bad_date: end_date "${data.end_date}"`);
  if (isDate(data.start_date) && isDate(data.end_date) && !(data.end_date > data.start_date)) {
    errors.push('bad_term: end_date is not after start_date');
  }
  if (data.seats !== null && data.seats !== undefined && !(Number.isInteger(data.seats) && data.seats > 0)) {
    errors.push(`bad_seats: ${data.seats}`);
  }
  if (data.price_per_seat !== null && data.price_per_seat !== undefined && !(Number(data.price_per_seat) >= 0)) {
    errors.push(`bad_price: ${data.price_per_seat}`);
  }
  if (data.notice_days !== null && data.notice_days !== undefined
    && !(Number.isInteger(data.notice_days) && data.notice_days >= 0 && data.notice_days <= 365)) {
    errors.push(`bad_notice_days: ${data.notice_days} (expected 0 to 365)`);
  }
  // Accept common ways of writing a currency and turn them into the ISO code.
  const CURRENCY_NAMES = { 'US DOLLARS': 'USD', 'US DOLLAR': 'USD', 'DOLLARS': 'USD', '$': 'USD', 'EURO': 'EUR', 'EUROS': 'EUR', '€': 'EUR', 'POUNDS': 'GBP', '£': 'GBP' };
  if (typeof data.currency === 'string') data.currency = CURRENCY_NAMES[data.currency.trim().toUpperCase()] ?? data.currency.trim().toUpperCase();
  if (data.currency && !CURRENCIES.includes(data.currency)) errors.push(`unknown_currency: ${data.currency}`);
  if (data.billing_cycle && !['monthly', 'annual'].includes(data.billing_cycle)) errors.push(`bad_billing_cycle: ${data.billing_cycle}`);
  if (data.product && !knownTools.includes(String(data.product).trim().toLowerCase())) {
    errors.push(`unknown_product: "${data.product}" is not a tool we manage`);
  }
  // Some models answer on a 0 to 100 scale (99.5 instead of 0.995): accept that and normalise it.
  if (typeof data.confidence === 'number' && data.confidence > 1 && data.confidence <= 100) data.confidence /= 100;
  if (typeof data.confidence !== 'number' || data.confidence < 0.7) {
    errors.push(`low_confidence: ${data.confidence ?? 'none'} (needs at least 0.7)`);
  }

  // ---- 3. cross-check: seats x price against any "total" written in the document text ----
  // Independent of the model: we read the totals straight from the PDF text.
  const text = String($('Extract PDF').first().json.text ?? '');
  const totals = [...text.matchAll(/total[^\n\d]{0,60}?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)/gi)]
    .map((m) => Number(m[1].replace(/,/g, '')));
  if (totals.length > 0 && Number.isInteger(data.seats) && Number(data.price_per_seat) >= 0) {
    const monthly = data.seats * Number(data.price_per_seat);
    const candidates = [monthly, monthly * 12];
    if (!totals.some((t) => candidates.some((c) => Math.abs(c - t) <= 1))) {
      errors.push(`total_mismatch: the document states a total of ${totals.join(' / ')} but ${data.seats} seats x ${data.price_per_seat} gives ${monthly} per month or ${monthly * 12} per year`);
    }
  }

  // ---- 4. never overwrite an existing contract with different numbers ----
  const existing = existingByRef[data.contract_ref];
  if (existing) {
    const diffs = [];
    if (existing.seats !== data.seats) diffs.push(`seats ${existing.seats} vs ${data.seats}`);
    if (Math.abs(Number(existing.price_per_seat) - Number(data.price_per_seat)) > 0.005) diffs.push(`price ${existing.price_per_seat} vs ${data.price_per_seat}`);
    if (existing.start_date !== data.start_date) diffs.push(`start ${existing.start_date} vs ${data.start_date}`);
    if (existing.end_date !== data.end_date) diffs.push(`end ${existing.end_date} vs ${data.end_date}`);
    if (existing.notice_days !== data.notice_days) diffs.push(`notice ${existing.notice_days} vs ${data.notice_days}`);
    if (existing.auto_renew !== data.auto_renew) diffs.push(`auto_renew ${existing.auto_renew} vs ${data.auto_renew}`);
    if (diffs.length) errors.push(`conflicts_with_existing_contract ${data.contract_ref}: ${diffs.join(', ')}`);
    else warnings.push(`updates_existing_contract: ${data.contract_ref} already exists with the same values`);
  }
  if (data.currency && String(data.currency).toUpperCase() !== 'USD') warnings.push(`non_usd_currency: ${data.currency}`);
}

// ---- 5. result ----
const status = llmFailed ? 'failed' : (errors.length > 0 ? 'needs_review' : 'extracted');
const clean = data && {
  document_type: data.document_type, vendor: data.vendor, product: data.product, contract_ref: data.contract_ref,
  start_date: data.start_date, end_date: data.end_date, seats: data.seats, price_per_seat: data.price_per_seat,
  currency: data.currency ?? null, billing_cycle: data.billing_cycle,
  auto_renew: data.auto_renew, notice_days: data.notice_days, owner: data.owner ?? null,
};

return [{
  json: {
    status,
    valid: status === 'extracted',
    llm_failed: llmFailed,
    errors,
    warnings,
    data: clean,
    extracted: {
      data: clean, confidence: data?.confidence ?? null, evidence: data?.evidence ?? null,
      errors, warnings, provider: built.provider, model: built.model, text_chars: built.text_chars,
    },
  },
}];
