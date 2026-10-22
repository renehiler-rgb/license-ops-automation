// Code node "Shape findings"  (mode: Run Once for All Items)
// Input : the rows from the "Audit rules" Postgres node (one item per finding; turn on "Always Output Data").
// Output: ONE item { findings, total, by_type } -> "Upsert findings" gets findings as JSON.
// It drops empty rows, makes sure each finding is unique (the table has a unique key) and counts per type.

const ALLOWED = ['inactive_seat', 'orphaned_account', 'seat_mismatch', 'duplicate_account', 'over_allocation'];
const findings = [];
const byType = {};
const seen = new Set();

for (const item of $input.all()) {
  const f = item.json;
  if (!f.finding_type) continue;                            // the empty item from "Always Output Data"
  if (!ALLOWED.includes(f.finding_type)) continue;

  // Same key as the unique index in audit_findings: type + account (or 0) + email (or '')
  const key = `${f.finding_type}|${f.account_id ?? 0}|${f.employee_email ?? ''}`;
  if (seen.has(key)) continue;
  seen.add(key);

  findings.push({
    finding_type: f.finding_type,
    account_id: f.account_id ?? null,
    employee_email: f.employee_email ?? null,
    severity: f.severity,
    details: f.details ?? {},
  });
  byType[f.finding_type] = (byType[f.finding_type] ?? 0) + 1;
}

return [{ json: { findings, total: findings.length, by_type: byType } }];
