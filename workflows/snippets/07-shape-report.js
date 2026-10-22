// Code node "Shape report"  (mode: Run Once for All Items)
// Input : the row from "Compute report" ({ report: { month, by_tool, by_team_tool } }).
// Output: ONE item { month, totals, by_tool, by_team_tool }.
//   totals = overall numbers, top 3 variances, top 3 idle-cost tools, biggest month-over-month movers.
// "totals" is what gets stored in monthly_reports and (aggregates only) sent to the local model.

const report = $input.first().json.report;
const byTool = report.by_tool ?? [];
const byTeamTool = report.by_team_tool ?? [];
if (byTool.length === 0) throw new Error(`No spend data for ${report.month}`);

const round2 = (x) => Math.round(Number(x) * 100) / 100;
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const sum = (rows, key) => round2(rows.reduce((total, row) => total + Number(row[key] ?? 0), 0));
const pct = (part, whole) => (whole ? Math.round((part / whole) * 1000) / 10 : null);

// Overall
const actual = sum(byTool, 'actual');
const budget = sum(byTool, 'budget');
const activeUsers = sum(byTool, 'active_users');
const prevActual = sum(byTool.filter((t) => t.prev_actual !== null), 'prev_actual');
const overall = {
  actual, budget,
  variance: round2(actual - budget),
  variance_pct: pct(actual - budget, budget),
  committed: sum(byTool, 'committed'),
  usage_spend: sum(byTool, 'usage_spend'),
  active_users: activeUsers,
  cost_per_active_user: activeUsers ? round2(actual / activeUsers) : null,
  idle_cost: sum(byTool, 'idle_cost'),
  prev_actual: prevActual || null,
  mom_change: prevActual ? round2(actual - prevActual) : null,
  mom_pct: prevActual ? pct(actual - prevActual, prevActual) : null,
};

// Top 3 team + tool combinations over budget (only rows that have a budget)
const topVariances = byTeamTool
  .filter((r) => r.budget !== null && Number(r.variance) > 0)
  .sort((a, b) => b.variance - a.variance)
  .slice(0, 3)
  .map((r) => ({ team: r.team, tool: r.tool, actual: r.actual, budget: r.budget, variance: r.variance, variance_pct: r.variance_pct }));

// Teams whose total across all tools is over budget
const teamTotals = {};
for (const r of byTeamTool.filter((row) => row.budget !== null)) {
  const t = (teamTotals[r.team] ??= { actual: 0, budget: 0 });
  t.actual += Number(r.actual);
  t.budget += Number(r.budget);
}
const teamsOverBudget = Object.entries(teamTotals)
  .filter(([, t]) => t.actual > t.budget)
  .map(([team, t]) => ({ team, variance: round2(t.actual - t.budget), variance_pct: pct(t.actual - t.budget, t.budget) }))
  .sort((a, b) => b.variance - a.variance);

// Top 3 tools by idle cost
const topIdle = [...byTool]
  .sort((a, b) => b.idle_cost - a.idle_cost)
  .slice(0, 3)
  .map((t) => ({ tool: t.tool, idle_cost: t.idle_cost }));

// Biggest month-over-month movers (needs a previous month)
const momMovers = byTool
  .filter((t) => t.mom_change !== null)
  .sort((a, b) => Math.abs(b.mom_change) - Math.abs(a.mom_change))
  .slice(0, 3)
  .map((t) => ({ tool: t.tool, mom_change: t.mom_change, mom_pct: t.mom_pct, actual: t.actual, prev_actual: t.prev_actual }));

const totals = {
  month: report.month,
  currency: 'USD',
  overall,
  teams_over_budget: teamsOverBudget,
  top_variances: topVariances,
  top_idle_tools: topIdle,
  mom_movers: momMovers,
};

return [{ json: { month: report.month, totals, by_tool: byTool, by_team_tool: byTeamTool, total_text: usd.format(actual) } }];
