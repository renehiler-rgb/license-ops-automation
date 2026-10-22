# RAG evaluation

How well does the contract Q&A (workflow C2) work? `scripts/eval_rag.py` answers that with numbers instead of "I tried a few questions".

```
python3 scripts/eval_rag.py                    # search + full answers (needs n8n, Ollama, the model)
python3 scripts/eval_rag.py --retrieval-only   # only the search step, takes seconds, no language model
python3 scripts/eval_rag.py --json report.json
```

On a host where Ollama listens on the docker bridge, prefix with `OLLAMA_HOST=172.17.0.1:11434`.

## What is measured

The 20 questions are in `scripts/rag_eval_questions.json`: 16 the contracts answer and 4 they do not (out of scope, and one prompt-injection attempt). For each answerable question the file says which contract holds the answer, the words in the passage that contain it, and the facts a correct answer must state.

**Retrieval.** The question is embedded and searched with the same SQL file the workflow uses (`workflows/snippets/sql/search_chunks.sql`). A passage only counts as correct if it comes from the right contract **and** contains the answer text. (Matching the contract alone is too generous: my first version did that and reported 100%.) Reported as hit@1, hit@3, hit@6 and MRR (average of 1/rank).

**Answers.** Each question goes through the real webhook. Checks: the answer contains every expected fact, a returned source is an expected file or the contracts table, out-of-scope questions get exactly "That is not in the contracts." with no sources, and answerable questions are not refused.

## Result (qwen2.5:32b, nomic-embed-text, 6 contracts, 19 passages, Oct 2026)

| Measure | Result |
|---|---|
| Retrieval hit@1 | 9/14 (64%) |
| Retrieval hit@3 | 12/14 (86%) |
| Retrieval hit@6 | 12/14 (86%) |
| Retrieval MRR | 0.71 |
| Correct facts in the answer | 14/16 (88%) |
| Answer cites a valid source | 15/16 (94%) |
| False refusals | 1/16 (6%) |
| Out-of-scope questions refused | 4/4 (100%) |

Two full runs gave identical results. The 14 retrieval questions are those with a known passage; "Which contracts auto-renew?" and "Which contract ends first?" are answered from the contracts table and have none.

## The failures, and what they show

- **q04, "What service credit does CodeForge give if availability falls below the target?"**: a real retrieval miss and a false refusal. The passage with the answer (section 6, service levels) ranks below the top 6 because the other CodeForge passages score higher: the two CodeForge contracts crowd out the one that matters, and "service credit" is a keyword the embedding does not weigh enough. The model then correctly said it had no answer. This is the safe failure (a refusal, not an invention), but it is still a wrong result. Consistent in 3 repeated calls.
- **q08, "How many seats does MeetSpace have and what does one seat cost?"**: the passage is not in the top 6, but the answer is right because the structured contracts table is always part of the context. That is what the hybrid design is for.
- **q16, "Who is the contract owner named in the MeetSpace agreement?"**: retrieval was fine, the model answered "Northwind Media d.o.o." (the customer) and not the contact address. A model reading error, not a search problem.
- **q03, q06, q12**: the answer passage is found at rank 3, not 1. The two DesignHub contracts share wording and neighbouring passages overlap by design, so near-duplicate passages rank ahead of it. The answer was right every time because those passages carry the same text.

## What I would change next

1. Return more passages (8 to 10 instead of 6) or add a keyword search next to the vector search (Postgres full-text) and merge the two lists. This targets q04 directly.
2. Add a reranking step.
3. A larger and messier document set. With 19 passages this is a design check, not a scale test, and hit@6 covers a third of the corpus.

I did not change the workflow to make these numbers look better: the point is to know where it breaks.
