// Code node "Make CSV"  (mode: Run Once for All Items)
// Input : "Shape report". Output: ONE item { csv, file_name } -> "Convert to File" (operation "Convert to Text File",
//   Source Property = csv, File Name = {{ $json.file_name }}), then the Slack file upload.
// One row per team and tool, same numbers as the report.

const { month, by_team_tool: rows } = $('Shape report').first().json;

const columns = ['team', 'tool', 'actual', 'budget', 'variance', 'variance_pct',
  'accounts', 'active_users', 'cost_per_active_user', 'idle_cost'];

// Wrap a value in quotes only when it needs them (comma, quote or line break)
function cell(value) {
  if (value === null || value === undefined) return '';
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

const lines = [columns.join(',')];
for (const row of rows) lines.push(columns.map((c) => cell(row[c])).join(','));

return [{ json: { csv: lines.join('\n') + '\n', file_name: `spend-${month}.csv` } }];
