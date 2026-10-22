// Code node "Resolve month"  (mode: Run Once for All Items)
// Input : the Webhook (POST /webhook/spend-report, body {"month": "2026-09"}), the schedule or the manual trigger.
// Output: ONE item { valid, error, month_start: "2026-09-01", month_label: "2026-09" }.
//   Schedule / manual run: the previous calendar month.
//   Webhook run: the month from the body; it must look like YYYY-MM and must not be in the future.

const pad = (n) => String(n).padStart(2, '0');
const now = new Date();
const thisMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;

// Previous month as "YYYY-MM"
const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
const previousMonth = `${prev.getFullYear()}-${pad(prev.getMonth() + 1)}`;

const body = $input.first().json.body ?? {};
const requested = body.month === undefined ? previousMonth : String(body.month).trim();

let error = null;
if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(requested)) error = 'month must look like 2026-09';
else if (requested > thisMonth) error = `month ${requested} is in the future`;

return [{
  json: {
    valid: error === null,
    error,
    month_start: `${requested}-01`,
    month_label: requested,
  },
}];
