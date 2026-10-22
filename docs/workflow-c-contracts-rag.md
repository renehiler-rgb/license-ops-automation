# Workflow C: Contract intake and "ask the contracts"

Exports: `workflows/c1-contract-intake.json`, `workflows/c2-ask-contracts.json`, `workflows/r-replay-dead-letter.json`.
Code and SQL per node: `workflows/snippets/` (files `15`-`24`, `sql/`). Test PDFs: `sample-contracts/` (made by `scripts/make_contract_pdfs.py`).

Everything runs locally by default: text extraction in n8n, the language model and the embeddings in Ollama, vectors in Postgres (pgvector).
`app_config.llm_provider = "anthropic"` switches extraction and answers to Claude (optional, needs an Anthropic credential in n8n).

## C1: contract intake
`POST /webhook/contract-intake` (multipart, field `file`, header `X-Intake-Key`). From the shell: `scripts/post_contract.sh file.pdf`.

```
Webhook -> Read upload (checks) -> Extract PDF -> Config -> Run log
  -> Hash and lookup (sha256 in Postgres) -> already stored? -> respond "duplicate"
  -> Load reference data -> Build request -> LLM (Ollama or Claude) -> Validate extraction
  -> Store document -> Upsert contract (only when valid) -> Slack review (when not valid)
  -> Chunk text -> Save chunks -> Embed chunks (Ollama) -> Save embeddings -> Respond -> Run log
```

- **Answer:** `{document_id, status, contract_ref, warnings[], errors[], indexed}`. `status` is `extracted`, `needs_review`, `failed` or `duplicate`.
- **Structured output:** the model must return a fixed schema (vendor, product, contract_ref, dates, seats, price per seat, currency, billing cycle, auto-renew, notice days, owner, confidence, evidence quotes). Ollama gets it as `format`, Claude as a forced tool (`record_contract`).
- **Validation** (a Code node that returns named reasons, never throws on bad model output): required fields, real dates and end after start, seats > 0, price >= 0, notice days 0-365, known currency, known product, confidence >= 0.7,
  the seats x price against any total written in the PDF text, and **no overwrite of an existing contract with different numbers** (that goes to review instead).
- **Idempotency:** the file hash is unique, so a file that was already extracted is a no-op (`duplicate`). A `needs_review` or `failed` file is processed again when re-sent, so a fix can be applied. Contracts are keyed by `contract_ref`; chunks by `(document_id, chunk_index)`.
- **Chunking:** about 800 characters with 150 overlap, each chunk starts with its section titles. The text is saved first, the embedding second, so an embedding failure never loses the contract.
- **Security:** the document text is treated as data (the prompt says to ignore instructions inside it); the file must be a PDF under 15 MB; the webhook needs the key.

## C2: ask the contracts
`POST /webhook/ask-contracts` with `{"question": "..."}` and the same header, or the hosted chat page of the Chat Trigger (requires an n8n login, so it is not open to anyone who can reach the port).

```
question -> embed (Ollama) -> top 6 chunks by cosine distance (pgvector) + all structured contract rows
  -> model answers ONLY from that context, with citations -> answer + sources
```
The answer must cite `[file.pdf, section]` or `[contracts table, contract_ref]`. If the answer is not in the context the model must reply "That is not in the contracts."
`sources` in the response lists the passages the answer actually cites. If Ollama's embedding is down the question is still answered from the structured table (no passages).
Slack slash commands would need a public endpoint; this n8n is deliberately private (localhost / Tailscale), so they are not used.

## R: dead-letter replay
`POST /webhook/replay-dead-letter` (or run manually): for every open `C1 - Contract intake / Embed chunks` entry it embeds the chunks that still have no embedding, saves them and marks the entry `replayed`. A failing replay stays open and counts the attempt.

## Config (`app_config`)
`llm_provider`, `ollama_url`, `ollama_extract_model` (extraction and answers), `ollama_embed_model`, `slack_channel_alerts` (review messages), `rag_min_similarity` (optional, default 0.3), `anthropic_model` (only with the Claude switch).

## Known limits
- A model can misread a document. The checks above catch most of it, but for a **new** contract (no existing record to compare with) a plausible wrong value, for example the 30-day breach period read as the notice period, would pass. `docs/failure-testing.md` shows this with the deliberately messy sample. Use a stronger model, or review low-confidence documents.
- Scanned PDFs without text are sent to review (no OCR).
- The answers are only as good as the local model. `llama3.1:8b` answers are loose; `qwen2.5:32b` is clearly better (see failure-testing.md).
