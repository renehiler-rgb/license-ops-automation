// Code node "Normalise usage"  (mode: Run Once for All Items)
// Reads the four vendor usage lists BY NODE NAME, so the HTTP nodes must be called exactly:
//   "Chatterly usage", "DesignHub usage", "CodeForge activity", "MeetSpace activity"
// Maps every vendor to:  { tool, external_id, day (YYYY-MM-DD), activity_count, spend_usd }
// Output: one item per batch of up to 2000 rows { usage, rejected, items_in, items_out, batch, batches }.
//   "Upsert usage" runs once per batch. rejected, items_in, items_out and bad_pages are the totals (same on every batch).

const BATCH_SIZE = 2000;

// A real calendar day written as YYYY-MM-DD, or null.
function checkDay(text) {
  if (typeof text !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(text)) return null;
  return Number.isNaN(Date.parse(text)) ? null : text;
}
// MeetSpace sends the start of the day as epoch seconds (UTC) -> "YYYY-MM-DD"
function dayFromEpochSeconds(n) {
  return typeof n === 'number' ? checkDay(new Date(n * 1000).toISOString().slice(0, 10)) : null;
}
const round2 = (n) => Math.round(Number(n) * 100) / 100;

const VENDORS = [
  {
    tool: 'chatterly', node: 'Chatterly usage', list: (p) => p.data,
    map: (r) => ({ external_id: r.user_id, day: checkDay(r.date), activity_count: r.requests, spend_usd: r.cost_usd }),
  },
  {
    tool: 'designhub', node: 'DesignHub usage', list: (p) => p.items,
    map: (r) => ({
      external_id: r.id,
      day: checkDay(String(r.day).replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3')),   // 20260105 -> 2026-01-05
      activity_count: r.actions, spend_usd: Number(r.spend_cents) / 100,             // cents -> dollars
    }),
  },
  {
    tool: 'codeforge', node: 'CodeForge activity', list: (p) => p.events,
    map: (r) => ({ external_id: r.member_id, day: checkDay(r.date), activity_count: r.contributions, spend_usd: 0 }),
  },
  {
    tool: 'meetspace', node: 'MeetSpace activity', list: (p) => p.results,
    map: (r) => ({ external_id: r.uid, day: dayFromEpochSeconds(r.day_start), activity_count: r.meetings, spend_usd: 0 }),
  },
];

function pagesOf(nodeName) {
  try { return $(nodeName).all().map((i) => i.json); } catch (e) { return []; }
}

const byKey = new Map();      // tool|external_id|day -> row (a repeated row replaces the earlier one)
const rejected = [];
let itemsIn = 0;

let badPages = 0;      // pages without the vendor's list (error bodies); they are skipped and counted

for (const vendor of VENDORS) {
  for (const page of pagesOf(vendor.node)) {
    if (!Array.isArray(vendor.list(page))) { badPages += 1; continue; }
    for (const raw of vendor.list(page)) {
      itemsIn += 1;
      const row = { tool: vendor.tool, ...vendor.map(raw) };

      let reason = null;
      if (!row.external_id) reason = 'missing external_id';
      else if (!row.day) reason = 'unparseable day';
      else if (!Number.isInteger(row.activity_count) || row.activity_count < 0) reason = 'invalid activity_count';
      else if (!Number.isFinite(row.spend_usd) || row.spend_usd < 0) reason = 'invalid spend';

      if (reason) {
        rejected.push({ item: { tool: vendor.tool, ...raw }, reason });
        continue;
      }
      row.spend_usd = round2(row.spend_usd);
      byKey.set(`${row.tool}|${row.external_id}|${row.day}`, row);
    }
  }
}

const rows = [...byKey.values()];
const batches = Math.max(1, Math.ceil(rows.length / BATCH_SIZE));
const out = [];
for (let i = 0; i < batches; i += 1) {
  out.push({
    json: {
      usage: rows.slice(i * BATCH_SIZE, (i + 1) * BATCH_SIZE),
      rejected, items_in: itemsIn, items_out: rows.length, bad_pages: badPages, batch: i + 1, batches,
    },
  });
}
return out;
