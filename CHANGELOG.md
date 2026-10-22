# Changelog

## Unreleased
- `scripts/eval_rag.py` and `docs/rag-evaluation.md`: 20-question evaluation of the contract Q&A (retrieval hit@k and MRR, answer correctness, citations, refusals).

## v1.0.0

First release.

**Workflows (9, n8n)**
- A: daily usage and activity audit across four vendor APIs (API key and OAuth2, cursor and page pagination) and an HR directory; five audit rules; one Slack digest of new findings.
- B: monthly spend and budget report per tool and team; summary by a local model from aggregated numbers; Slack post with a CSV; on-demand webhook.
- C: contract intake (PDF, structured extraction, named validation checks, upsert, chunking, embeddings in pgvector) and a question-answering workflow with citations.
- D: renewal alerts at 90, 60 and 30 days with an optional Jira ticket.
- E, F, R: shared error handler, weekly health summary, dead-letter replay.

**Reliability**
- Idempotent writes everywhere; every workflow re-run twice with zero duplicates.
- Retries, partial-vendor results, dead letters with replay, a run log, and an error handler that still alerts when Postgres is down.
- Renewal alerts are claimed before sending and confirmed after, so overlapping or crashed runs neither duplicate nor lose an alert.
- Failure testing documented in `docs/failure-testing.md`.

**Local by default**
- Everything runs on one machine with Ollama (no API key needed). User and activity data never leaves it. An Anthropic switch exists for contract extraction and answers.

**Setup**
- `scripts/bootstrap.sh` sets up a fresh clone in about a minute; the same steps by hand in `docs/manual-setup.md`.
- All ports on `127.0.0.1`; every webhook needs a header key.
- All data is synthetic; vendor APIs are mocks.
