// Code node "Plan ticket"  (mode: Run Once for Each Item)   [only runs when jira_enabled is true]
// Input : the answer of "Jira search" (open issues with the contract's label). The contract comes from "Claim alert".
// Output: { create, existing_key, jira_note, ticket } -> "Create ticket?" -> "Jira create".
// Rules:
//   - an open issue with the contract label exists -> reuse its key, never create a second one
//   - the search itself failed -> do NOT create (we cannot tell if one exists), say so in the note
//   - no open issue -> create one, but only at the first (largest) threshold, the 90-day mark

const contract = $('Claim alert').item.json;
const cfg = $('Config').first().json.cfg;
const search = $json;

if (search.error) {
  return { json: { create: false, existing_key: null, jira_note: `Jira search failed: ${search.error.message ?? search.error}` } };
}
const found = (search.issues ?? [])[0];
if (found) return { json: { create: false, existing_key: found.key, jira_note: null } };

const first = Math.max(...(cfg.renewal_thresholds ?? [90]));
if (contract.threshold_days !== first) {
  return { json: { create: false, existing_key: null, jira_note: null } };
}

const tool = `${contract.tool} (${contract.contract_ref})`;
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const ticket = {
  fields: {
    project: { key: cfg.jira_project_key },
    issuetype: { name: cfg.jira_issue_type ?? 'Task' },
    summary: `Renewal review: ${tool}, notice by ${String(contract.notice_deadline).slice(0, 10)}`,
    description: `Contract ${contract.contract_ref} for ${contract.tool} (${contract.vendor}) ends on ${String(contract.end_date).slice(0, 10)}.\n`
      + `Notice deadline: ${String(contract.notice_deadline).slice(0, 10)} (${contract.days_left} days).\n`
      + `Seats: ${contract.seats} · annual value ${money.format(contract.annual_value)}\n`
      + `Owner: ${contract.owner_email}\n\nPlease review usage and decide: renew, resize or cancel.\nCreated automatically by n8n (workflow D).`,
    labels: [contract.contract_ref, 'license-renewal'],
  },
};
return { json: { create: true, existing_key: null, jira_note: null, ticket } };
