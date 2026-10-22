// Code node "Build digest"  (mode: Run Once for All Items)
// Input : the rows from "Select new findings" (Always Output Data on, so an empty result is one empty item).
// Output: ONE item { skip, text, blocks, finding_ids }
//   skip = true when there is nothing to post (no new findings and post_empty_digest is false)
// Slack node: Message Type "Blocks", Blocks = {{ JSON.stringify({ blocks: $json.blocks }) }}, Text = {{ $json.text }}

const TOP_N = 5;
const TITLES = {
  orphaned_account: ':ghost: Orphaned accounts',
  inactive_seat: ':zzz: Inactive seats',
  duplicate_account: ':busts_in_silhouette: Duplicate accounts',
  seat_mismatch: ':arrows_counterclockwise: Premium seats barely used',
  over_allocation: ':warning: More accounts than licensed seats',
};
const ORDER = ['orphaned_account', 'over_allocation', 'inactive_seat', 'duplicate_account', 'seat_mismatch'];

const cfg = $('Config').first().json.cfg;
const findings = $input.all().map((i) => i.json).filter((f) => f.finding_type);
const accountsChecked = $('Normalise accounts').first().json.items_out;
const vendors = $('Normalise accounts').first().json.vendors;
const vendorNames = { chatterly: 'Chatterly AI', designhub: 'DesignHub', codeforge: 'CodeForge', meetspace: 'MeetSpace' };

const money = (n) => `$${Math.round(n).toLocaleString('en-US')}`;
const cost = (f) => Number(f.details?.monthly_cost ?? 0);

// "3/4 vendors synced, DesignHub failed"
const failed = Object.entries(vendors).filter(([, v]) => !v.ok).map(([k]) => vendorNames[k]);
const syncLine = failed.length === 0
  ? `${Object.keys(vendors).length}/${Object.keys(vendors).length} vendors synced`
  : `${Object.keys(vendors).length - failed.length}/${Object.keys(vendors).length} vendors synced, ${failed.join(', ')} failed`;

// Nothing new: post one short line, or nothing at all (setting post_empty_digest), unless a vendor failed
if (findings.length === 0) {
  const text = `No new findings, ${accountsChecked} accounts checked. ${syncLine}.`;
  // A failed vendor is always worth a message, even with no new findings.
  const skip = cfg.post_empty_digest !== true && failed.length === 0;
  const blocks = [{ type: 'section', text: { type: 'mrkdwn', text: `${failed.length > 0 ? ':warning: ' : ''}${text}` } }];
  return [{ json: { skip, text, blocks, finding_ids: [] } }];
}

// One line per finding
function line(f) {
  const d = f.details ?? {};
  const who = f.employee_email ?? '';
  switch (f.finding_type) {
    case 'orphaned_account': return `• ${who} — ${d.tool}, ${d.reason === 'terminated' ? 'employee has left' : 'not in HR'}, ${money(cost(f))}/mo`;
    case 'inactive_seat': return `• ${who} — ${d.tool}, last active ${String(d.last_active_at ?? 'never').slice(0, 10)}, ${money(cost(f))}/mo`;
    case 'duplicate_account': return `• ${who} — ${d.tool}, extra account ${d.external_id}, ${money(cost(f))}/mo`;
    case 'seat_mismatch': return `• ${who} — ${d.tool}, premium but ${d.active_days} active days in ${d.window_days}`;
    case 'over_allocation': return `• ${d.tool} — ${d.accounts} accounts for ${d.seats} seats (${d.excess} over, ${money(cost(f))}/mo)`;
    default: return `• ${who}`;
  }
}

const savings = findings.reduce((sum, f) => sum + cost(f), 0);
const blocks = [
  { type: 'header', text: { type: 'plain_text', text: 'License audit: new findings' } },
  {
    type: 'section',
    text: { type: 'mrkdwn', text: `*${findings.length} new findings*, about *${money(savings)}/month* at stake` },
  },
  { type: 'context', elements: [{ type: 'mrkdwn', text: `${accountsChecked} accounts checked · ${syncLine}` }] },
  { type: 'divider' },
];

for (const type of ORDER) {
  const group = findings.filter((f) => f.finding_type === type);
  if (group.length === 0) continue;
  group.sort((a, b) => cost(b) - cost(a));                 // biggest cost first
  const groupCost = group.reduce((sum, f) => sum + cost(f), 0);
  const shown = group.slice(0, TOP_N).map(line);
  if (group.length > TOP_N) shown.push(`_…and ${group.length - TOP_N} more_`);
  blocks.push({
    type: 'section',
    text: { type: 'mrkdwn', text: `*${TITLES[type]}* (${group.length}${groupCost > 0 ? `, ${money(groupCost)}/mo` : ''})\n${shown.join('\n')}` },
  });
}

return [{
  json: {
    skip: false,
    text: `License audit: ${findings.length} new findings, about ${money(savings)}/month at stake`,
    blocks,
    finding_ids: findings.map((f) => f.id),
  },
}];
