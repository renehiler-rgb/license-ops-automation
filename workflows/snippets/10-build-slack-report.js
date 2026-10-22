// Code node "Build Slack report"  (mode: Run Once for All Items)
// Input : the summary from "Check summary" or "Check summary retry"; the numbers come from "Shape report".
// Output: ONE item { text, blocks } for the Slack node:
//   Message Type "Blocks", Blocks = {{ JSON.stringify({ blocks: $json.blocks }) }}, Text = {{ $json.text }}

// The summary comes from the first try, or from the retry when the first answer was not usable.
const check = $('Check summary retry').isExecuted ? $('Check summary retry').first().json : $('Check summary').first().json;
const { totals, by_tool: byTool } = $('Shape report').first().json;
const o = totals.overall;
const summary = check.summary;

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const signedPct = (p) => (p === null || p === undefined ? 'n/a' : `${p >= 0 ? '+' : ''}${p}%`);
const flag = (variance) => (variance > 0 ? ':red_circle:' : ':large_green_circle:');

// One "field" per tool: actual / budget and the variance (Slack allows 10 fields per section)
const fields = byTool.slice(0, 10).map((t) => ({
  type: 'mrkdwn',
  text: `*${t.tool}*\n${usd.format(t.actual)} / ${usd.format(t.budget)}  ${flag(t.variance)} ${signedPct(t.variance_pct)}`,
}));

const where = check.source === 'ollama'
  ? 'Summary written by the local model; only aggregated numbers were sent to it.'
  : 'Summary built from a template (the local model gave no usable answer).';

const blocks = [
  { type: 'header', text: { type: 'plain_text', text: `Spend report ${totals.month}` } },
  { type: 'section', text: { type: 'mrkdwn', text: `*${summary.headline}*` } },
  {
    type: 'section',
    text: {
      type: 'mrkdwn',
      text: `*Total* ${usd.format(o.actual)} vs budget ${usd.format(o.budget)} (${signedPct(o.variance_pct)})`
        + ` · idle seats ${usd.format(o.idle_cost)}`
        + (o.cost_per_active_user === null ? '' : ` · ${usd.format(o.cost_per_active_user)} per active user`),
    },
  },
  { type: 'section', fields },
  { type: 'section', text: { type: 'mrkdwn', text: summary.three_points.map((p) => `• ${p}`).join('\n') } },
  { type: 'section', text: { type: 'mrkdwn', text: `:dart: *Recommended action:* ${summary.recommended_action}` } },
  { type: 'context', elements: [{ type: 'mrkdwn', text: where }] },
];

return [{ json: { text: `Spend report ${totals.month}: ${summary.headline}`, blocks } }];
