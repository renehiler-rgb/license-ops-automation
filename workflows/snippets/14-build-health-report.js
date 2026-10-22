// Code node "Build health report"  (mode: Run Once for All Items)
// Input : the row from "Health query" ({ health: { since, workflows, dead_letter_open, dead_letter } }).
// Output: ONE item { text, blocks } for the Slack node:
//   Message Type "Blocks", Blocks = {{ JSON.stringify({ blocks: $json.blocks }) }}, Text = {{ $json.text }}

const h = $input.first().json.health;
const workflows = h.workflows ?? [];
const deadOpen = Number(h.dead_letter_open);

// Green at 100%, yellow when something only half worked, red when runs failed
function icon(w) {
  if (w.failed > 0) return ':red_circle:';
  if (w.partial > 0) return ':large_yellow_circle:';
  return ':large_green_circle:';
}
const seconds = (s) => (s === null || s === undefined ? 'n/a' : s >= 60 ? `${Math.round(s / 6) / 10} min` : `${s} s`);

const lines = workflows.map((w) => {
  const rate = w.success_rate === null ? 'n/a' : `${w.success_rate}%`;
  const detail = [`${w.ok} ok`];
  if (w.partial) detail.push(`${w.partial} partial`);
  if (w.failed) detail.push(`${w.failed} failed`);
  if (w.running) detail.push(`${w.running} running`);
  return `${icon(w)} *${w.workflow}*: ${rate} success (${w.runs} runs: ${detail.join(', ')}), average ${seconds(w.avg_seconds)}`;
});

const totalRuns = workflows.reduce((sum, w) => sum + w.runs, 0);
const totalBad = workflows.reduce((sum, w) => sum + w.failed + w.partial, 0);
const headline = totalRuns === 0
  ? 'No workflow runs in the last 7 days'
  : `${totalRuns} runs in the last 7 days, ${totalBad === 0 ? 'all clean' : `${totalBad} not clean`}, ${deadOpen} open dead-letter item${deadOpen === 1 ? '' : 's'}`;

const blocks = [
  { type: 'header', text: { type: 'plain_text', text: 'Weekly workflow health' } },
  { type: 'section', text: { type: 'mrkdwn', text: `*${headline}*` } },
];
if (lines.length) blocks.push({ type: 'section', text: { type: 'mrkdwn', text: lines.join('\n') } });
else blocks.push({ type: 'section', text: { type: 'mrkdwn', text: ':warning: Nothing ran. Check that the schedules are published.' } });

if (deadOpen > 0) {
  const dead = h.dead_letter.map((d) => `• ${d.workflow}: ${d.open_items} open, oldest ${d.oldest_days} days`);
  blocks.push({ type: 'section', text: { type: 'mrkdwn', text: `*Open dead-letter items*\n${dead.join('\n')}` } });
}
blocks.push({ type: 'context', elements: [{ type: 'mrkdwn', text: `Runs since ${h.since}. "Partial" means the run finished but a source or step failed.` }] });

return [{ json: { text: `Weekly workflow health: ${headline}`, blocks } }];
