// Code node "Build review message"  (mode: Run Once for All Items)
// Input : any item; reads "Validate extraction", "Read upload" and "Store document" by name.
// Output: { text, blocks } for the Slack node: "please review this contract document", with the reasons.

const verdict = $('Validate extraction').first().json;
const filename = $('Read upload').first().json.filename;
const documentId = $('Store document').first().json.document_id;

const reasons = verdict.errors.map((e) => `• ${e}`).join('\n');
const extra = verdict.warnings.length ? `\n_Warnings:_ ${verdict.warnings.join('; ')}` : '';

return [{
  json: {
    text: `Contract document needs review: ${filename}`,
    blocks: [
      { type: 'section', text: { type: 'mrkdwn', text: `:mag: *Please review* \`${filename}\` (document ${documentId})` } },
      { type: 'section', text: { type: 'mrkdwn', text: `*Why it was not accepted automatically*\n${reasons}${extra}` } },
      { type: 'context', elements: [{ type: 'mrkdwn', text: 'Nothing was written to the contracts table. Fix the document or the data and send it again.' }] },
    ],
  },
}];
