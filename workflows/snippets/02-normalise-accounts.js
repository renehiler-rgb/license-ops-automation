// Code node "Normalise accounts"  (mode: Run Once for All Items)
// Reads the four vendor user lists BY NODE NAME, so the HTTP nodes must be called exactly:
//   "Chatterly users", "DesignHub users", "CodeForge members", "MeetSpace members"
// Each vendor uses different field names and date formats; this maps all of them to one shape:
//   { tool, external_id, email, seat_type, status, created_at, last_active_at }
// Output: ONE item { accounts, rejected, vendors, items_in, items_out }.
//   vendors tells the digest which vendors answered, e.g. { chatterly: { ok: true, count: 122 }, ... }

// ---- date helpers: each returns an ISO timestamp string, or null if the value is not a valid date ----
function fromEpochSeconds(n) { return toIso(typeof n === 'number' ? new Date(n * 1000) : null); }
function fromEpochMillis(n) { return toIso(typeof n === 'number' ? new Date(n) : null); }
function fromText(s) {
  // "2024-12-17 09:01:00" (DesignHub, UTC) needs a "T" and a "Z"; "2024-01-17T09:19:00Z" already has them
  if (typeof s !== 'string') return null;
  const text = s.includes('T') ? s : s.replace(' ', 'T') + 'Z';
  return toIso(new Date(text));
}
function toIso(date) { return date && !Number.isNaN(date.getTime()) ? date.toISOString() : null; }

// ---- one entry per vendor: where its list is, and how to turn one record into our shape ----
const VENDORS = [
  {
    tool: 'chatterly', node: 'Chatterly users', list: (p) => p.data,
    map: (u) => ({
      external_id: u.user_id, email: u.email,
      seat_type: u.plan === 'pro' ? 'premium' : 'standard',
      status: u.state === 'active' ? 'active' : 'inactive',
      created_at: fromEpochSeconds(u.created), last_active_at: fromEpochSeconds(u.last_seen),
    }),
  },
  {
    tool: 'designhub', node: 'DesignHub users', list: (p) => p.items,
    map: (u) => ({
      external_id: u.id, email: u.email_address,
      seat_type: u.role === 'creator' ? 'premium' : 'standard',
      status: u.is_active ? 'active' : 'inactive',
      created_at: fromText(u.joined_at), last_active_at: fromText(u.last_login),
    }),
  },
  {
    tool: 'codeforge', node: 'CodeForge members', list: (p) => p.members,
    map: (u) => ({
      external_id: u.member_id, email: u.login,
      seat_type: u.license === 'enterprise' ? 'premium' : 'standard',
      status: u.suspended ? 'inactive' : 'active',
      created_at: fromText(u.joined), last_active_at: fromText(u.last_activity),
    }),
  },
  {
    tool: 'meetspace', node: 'MeetSpace members', list: (p) => p.results,
    map: (u) => ({
      external_id: u.uid, email: u.mail,
      seat_type: u.tier === 'host' ? 'premium' : 'standard',
      status: String(u.status).toUpperCase() === 'ACTIVE' ? 'active' : 'inactive',
      created_at: fromEpochMillis(u.created_at), last_active_at: fromEpochMillis(u.last_active_at),
    }),
  },
];

// Items of a node by name. A vendor that failed has no items (or never ran), which is not an error here.
function pagesOf(nodeName) {
  try { return $(nodeName).all().map((i) => i.json); } catch (e) { return []; }
}

const accounts = [];
const rejected = [];
const vendors = {};
const seen = new Set();
let itemsIn = 0;

for (const vendor of VENDORS) {
  const pages = pagesOf(vendor.node);
  // A page without the vendor's list is an error body (for example {"detail": "Too many requests"}), not data.
  const hasAllLists = pages.every((page) => Array.isArray(vendor.list(page)));
  vendors[vendor.tool] = { ok: pages.length > 0 && hasAllLists, count: 0 };
  if (!hasAllLists) continue;                // do not use half a vendor; the digest reports it as failed

  for (const page of pages) {
    for (const raw of vendor.list(page)) {
      itemsIn += 1;
      const account = { tool: vendor.tool, ...vendor.map(raw) };
      const email = String(account.email ?? '').trim().toLowerCase();

      let reason = null;
      if (!account.external_id) reason = 'missing external_id';
      else if (!email.includes('@')) reason = 'missing or invalid email';
      else if (!account.created_at) reason = 'unparseable created date';
      else if (!account.last_active_at) reason = 'unparseable last-active date';
      else if (seen.has(`${vendor.tool}|${account.external_id}`)) reason = 'duplicate external_id in this run';

      if (reason) {
        rejected.push({ item: { tool: vendor.tool, ...raw }, reason });
        continue;
      }
      seen.add(`${vendor.tool}|${account.external_id}`);
      account.email = email;        // lower-cased and trimmed; a "+alias" is kept on purpose (the audit needs it)
      accounts.push(account);
      vendors[vendor.tool].count += 1;
    }
  }
}

return [{ json: { accounts, rejected, vendors, items_in: itemsIn, items_out: accounts.length } }];
