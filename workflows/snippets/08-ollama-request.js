// Code node "Build Ollama request"  (mode: Run Once for All Items)
// Input : "Shape report" (and "Config" for the model name).
// Output: ONE item { request } -> the HTTP node sends  {{ JSON.stringify($json.request) }}  to Ollama /api/chat.
// Only aggregated numbers go to the model: tool and team names with money, never people or emails.
// "format" is a JSON schema, so Ollama is forced to answer in that shape.

const cfg = $('Config').first().json.cfg;
const t = $('Shape report').first().json.totals;

const facts = {
  month: t.month,
  currency: t.currency,
  overall: t.overall,
  teams_over_budget: t.teams_over_budget,
  top_variances_team_and_tool: t.top_variances,
  top_idle_cost_tools: t.top_idle_tools,
  biggest_month_over_month_changes: t.mom_movers,
};

const schema = {
  type: 'object',
  properties: {
    headline: { type: 'string' },
    three_points: { type: 'array', items: { type: 'string' }, minItems: 3, maxItems: 3 },
    recommended_action: { type: 'string' },
  },
  required: ['headline', 'three_points', 'recommended_action'],
};

const request = {
  model: cfg.ollama_summary_model ?? 'llama3.1:8b',
  stream: false,
  format: schema,
  options: { temperature: 0.2 },
  messages: [
    {
      role: 'system',
      content: 'You are a finance analyst writing a short monthly software-spend summary for a finance team. '
        + 'Use ONLY the numbers in the data you are given, copied exactly. Never calculate new numbers or percentages and never invent figures. Money is in USD. '
        + 'Answer with: a one-sentence headline, exactly three short points, and one recommended action.',
    },
    { role: 'user', content: `Monthly license spend data (JSON):\n${JSON.stringify(facts)}` },
  ],
};

return [{ json: { request } }];
