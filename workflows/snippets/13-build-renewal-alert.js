// Code node "Build alert"  (mode: Run Once for Each Item)
// Input : $json is one of
//   - the claimed alert itself (Jira is off),
//   - "Plan ticket" output with an existing key or a note (no new ticket needed),
//   - the answer of "Jira create" ({ key } or { error }).
// Output: { contract_id, threshold_days, ticket_key, text, blocks } for the Slack node.

const c = $('Claim alert').item.json;
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const day = (value) => String(value).slice(0, 10);

let ticketKey = $json.key ?? $json.existing_key ?? '';
let jiraNote = $json.jira_note ?? '';
if ($json.error) jiraNote = `Jira ticket could not be created: ${$json.error.message ?? $json.error}`;

const overdue = c.days_left < 0;
const when = overdue
  ? `notice deadline *passed ${-c.days_left} days ago* (${day(c.notice_deadline)})`
  : `notice deadline in *${c.days_left} days* (${day(c.notice_deadline)})`;
const outcome = c.auto_renew ? 'renews automatically unless cancelled' : 'expires unless renewed';

const lines = [
  `:alarm_clock: *${c.tool}* (${c.vendor}), contract ${c.contract_ref}: ${when}`,
  `The contract ends ${day(c.end_date)} and ${outcome}.`,
];
const blocks = [
  { type: 'section', text: { type: 'mrkdwn', text: lines.join('\n') } },
  {
    type: 'section',
    fields: [
      { type: 'mrkdwn', text: `*Seats*\n${c.seats}` },
      { type: 'mrkdwn', text: `*Annual value*\n${money.format(c.annual_value)} (${c.billing_cycle})` },
      { type: 'mrkdwn', text: `*Owner*\n${c.owner_email}` },
      { type: 'mrkdwn', text: `*Alert level*\n${c.threshold_days}-day notice` },
    ],
  },
];
const context = [];
if (ticketKey) context.push({ type: 'mrkdwn', text: `:ticket: Renewal review: *${ticketKey}*` });
if (jiraNote) context.push({ type: 'mrkdwn', text: `:warning: ${jiraNote}` });
if (context.length) blocks.push({ type: 'context', elements: context });

return {
  json: {
    contract_id: c.contract_id,
    threshold_days: c.threshold_days,
    contract_ref: c.contract_ref,
    ticket_key: ticketKey,
    text: `${c.tool} (${c.contract_ref}): notice deadline ${overdue ? 'passed' : `in ${c.days_left} days`}`,
    blocks,
  },
};
