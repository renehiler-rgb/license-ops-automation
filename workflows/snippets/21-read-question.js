// Code node "Read question"  (mode: Run Once for All Items)
// Input : the Chat Trigger item ({ chatInput, sessionId }) or the Webhook item ({ body: { question } }).
// Output: ONE item { ok, source: 'chat' | 'webhook', question, problem }.

const json = $input.first().json;
const isChat = json.chatInput !== undefined;
const question = String(isChat ? json.chatInput : (json.body?.question ?? '')).trim();

let problem = null;
if (!question) problem = 'No question received. Send {"question": "..."}.';
else if (question.length > 500) problem = 'The question is longer than 500 characters.';

return [{ json: { ok: problem === null, source: isChat ? 'chat' : 'webhook', question, problem } }];
