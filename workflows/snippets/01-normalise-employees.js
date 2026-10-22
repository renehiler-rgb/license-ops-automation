// Code node "Normalise employees"  (mode: Run Once for All Items)
// Input : the pages from the "HR employees" HTTP node (one item per page, each with an "employees" list).
// Output: ONE item { employees, rejected, items_in, items_out } -> feeds "Upsert employees".
// Anything that fails validation goes to "rejected" (it is stored in dead_letter, not dropped).

const employees = [];
const rejected = [];
let itemsIn = 0;

// "2024-01-15" -> "2024-01-15", null/empty -> null, anything else -> undefined (= invalid)
function cleanDate(value) {
  if (value === null || value === undefined || value === '') return null;
  const ok = /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
  return ok ? value : undefined;
}

for (const page of $input.all()) {
  for (const raw of page.json.employees ?? []) {
    itemsIn += 1;

    const email = String(raw.email ?? '').trim().toLowerCase();
    const status = String(raw.employment_status ?? '').trim().toLowerCase();   // ACTIVE -> active
    const startDate = cleanDate(raw.hire_date);
    const endDate = cleanDate(raw.termination_date);

    let reason = null;
    if (!email.includes('@')) reason = 'missing or invalid email';
    else if (!raw.full_name) reason = 'missing name';
    else if (!raw.department) reason = 'missing department';
    else if (!['active', 'terminated'].includes(status)) reason = `unknown status "${raw.employment_status}"`;
    else if (startDate === undefined || endDate === undefined) reason = 'unparseable date';

    if (reason) {
      rejected.push({ item: raw, reason });
      continue;
    }
    employees.push({
      email,
      name: String(raw.full_name).trim(),
      team: String(raw.department).trim(),
      cost_center: raw.cost_center ?? null,
      status,
      start_date: startDate,
      end_date: endDate,
    });
  }
}

return [{ json: { employees, rejected, items_in: itemsIn, items_out: employees.length } }];
