// Code node "Check summary" (first try) and "Check summary retry" (second try). Same code in both  (mode: Run Once for All Items)
// Input : the answer of the Ollama HTTP node. If Ollama was unreachable the item holds an "error" instead.
// Output: ONE item { ok, source, summary: { headline, three_points, recommended_action }, reason }.
//   First try fails      -> ok = false, the workflow asks Ollama once more.
//   Second try fails too -> a summary built from a template, source = 'template'. The report is never blocked.

// false in "Check summary" (first try), true in "Check summary retry" (second try, falls back to the template)
const isRetry = false;
const totals = $('Shape report').first().json.totals;
const input = $input.first().json;

// ---- 1. is the answer usable? ----
function parse(response) {
  if (response.error) return { reason: `Ollama call failed: ${response.error.message ?? response.error}` };
  let data;
  try {
    data = JSON.parse(response.message?.content ?? '');
  } catch (e) {
    return { reason: 'answer is not valid JSON' };
  }
  const text = (value) => typeof value === 'string' && value.trim().length > 0;
  if (!text(data.headline)) return { reason: 'missing headline' };
  if (!Array.isArray(data.three_points) || data.three_points.length !== 3 || !data.three_points.every(text)) {
    return { reason: 'three_points must be exactly 3 non-empty strings' };
  }
  if (!text(data.recommended_action)) return { reason: 'missing recommended_action' };
  return {
    summary: {
      headline: data.headline.trim(),
      three_points: data.three_points.map((p) => p.trim()),
      recommended_action: data.recommended_action.trim(),
    },
  };
}

const parsed = parse(input);
if (parsed.summary) return [{ json: { ok: true, source: 'ollama', summary: parsed.summary, reason: null } }];
if (!isRetry) return [{ json: { ok: false, source: null, summary: null, reason: parsed.reason } }];

// ---- 2. template summary (second failure) ----
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const signed = (n) => `${n >= 0 ? '+' : '-'}${usd.format(Math.abs(n))}`;
const o = totals.overall;
const top = totals.top_variances[0];
const idle = totals.top_idle_tools[0];
const mover = totals.mom_movers[0];

const points = [
  top
    ? `Largest overspend: ${top.team} on ${top.tool}, ${signed(top.variance)} over budget.`
    : 'No team is over budget on any tool.',
  idle
    ? `Idle seats cost ${usd.format(o.idle_cost)} in total; most of it is ${idle.tool} (${usd.format(idle.idle_cost)}).`
    : 'No idle seats were found.',
  mover
    ? `Biggest change from last month: ${mover.tool}, ${signed(mover.mom_change)}.`
    : 'No previous month to compare with.',
];
const summary = {
  headline: `${totals.month}: ${usd.format(o.actual)} spent against a ${usd.format(o.budget)} budget `
    + `(${o.variance >= 0 ? '+' : ''}${o.variance_pct ?? 0}%).`,
  three_points: points,
  recommended_action: idle
    ? `Review the idle ${idle.tool} seats and reclaim the unused ones.`
    : 'No action needed this month.',
};
return [{ json: { ok: true, source: 'template', summary, reason: parsed.reason } }];
