"""
eval_rag.py - measure how well the contract Q&A (workflow C2) works.

Run it after the sample contracts have been ingested (workflow C1):
  python3 scripts/eval_rag.py                    # retrieval + full answers (needs n8n, Ollama, the model)
  python3 scripts/eval_rag.py --retrieval-only   # only the search step, fast, no language model
  python3 scripts/eval_rag.py --json report.json # also write every result to a file

The questions and what a good answer looks like are in scripts/rag_eval_questions.json.

Two things are measured.

1. RETRIEVAL (does the search find the right passage?)
   The question is embedded and searched with the SAME SQL as workflow C2
   (workflows/snippets/sql/search_chunks.sql). For every question that names the file(s) holding
   the answer we record the rank of the first correct passage (right file AND the answer text in it).
     hit@1 / hit@3 / hit@6 = share of questions whose correct passage is in the top 1 / 3 / 6
     MRR                   = average of 1/rank (1.0 = always first, lower = found later or missed)
   Note: the sample set has only 19 passages, and the answer is read from the top 6,
   so hit@6 is easy here. hit@1 and MRR are the numbers that tell something.

2. ANSWERS (does the whole workflow answer correctly?)
   Each question is sent to POST /webhook/ask-contracts. Then we check:
     correct   = the answer contains every expected fact (regular expressions in the questions file)
     cited     = at least one returned source is an expected file (or the contracts table)
     refused   = for out-of-scope questions: the answer is exactly "That is not in the contracts."
                 and no sources are returned
     false refusal = the model refused a question that the contracts do answer

Connection settings (all optional):
  OLLAMA_HOST       where Ollama listens (default localhost:11434; on this host 172.17.0.1:11434)
  N8N_URL           default http://localhost:5678
  INTAKE_API_KEY    read from .env (never printed)
  POSTGRES_PASSWORD read from .env, PGHOST/PGPORT as in load_data.py

Exit code 0 = every answer check passed, 1 = at least one answer check failed, 2 = could not run.
Retrieval misses are reported but do not change the exit code (the contracts table can still answer).
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_data import ROOT, connect, read_env_file  # noqa: E402

QUESTIONS_FILE = ROOT / "scripts" / "rag_eval_questions.json"
SEARCH_SQL = ROOT / "workflows" / "snippets" / "sql" / "search_chunks.sql"
REFUSAL = "that is not in the contracts"
EMBED_MODEL = "nomic-embed-text"     # must be the model the chunks were embedded with


def post_json(url: str, body: dict, headers: dict, timeout: int) -> dict:
    """POST a JSON body and return the JSON answer. Raises on network or HTTP errors."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "localhost:11434")
    return host if host.startswith("http") else "http://" + host


def embed_question(question: str) -> str:
    """Embed a question like workflow C2 does and return it as pgvector text: '[0.1,0.2,...]'."""
    result = post_json(
        ollama_url() + "/api/embed",
        {"model": EMBED_MODEL, "input": ["search_query: " + question]},
        {},
        timeout=120,
    )
    return json.dumps(result["embeddings"][0])


def search_chunks(conn, embedding: str) -> list[dict]:
    """Run the real search query of workflow C2 and return the 6 closest passages, best first."""
    sql = SEARCH_SQL.read_text(encoding="utf-8").replace("$1", "%(embedding)s")
    cursor = conn.execute(sql, {"embedding": embedding})
    columns = [c.name for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def first_correct_rank(chunks: list[dict], item: dict) -> int | None:
    """1-based position of the first passage that really holds the answer, or None if there is none.

    A passage counts when it comes from an expected file AND its text matches the "evidence"
    expression of the question (the words that contain the answer). Checking the file alone would
    be too generous: a contract has several passages and only one of them answers the question.
    """
    evidence = item.get("evidence")
    for position, chunk in enumerate(chunks, start=1):
        if chunk["filename"] not in item["expected_files"]:
            continue
        if evidence is None or re.search(evidence, chunk["content"], re.IGNORECASE):
            return position
    return None


def ask(question: str, n8n_url: str, key: str) -> dict:
    """Send the question to the C2 webhook. Returns the JSON answer, or {'error': ...}."""
    try:
        return post_json(n8n_url + "/webhook/ask-contracts", {"question": question},
                         {"X-Intake-Key": key}, timeout=300)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return {"error": str(error)}


def check_answer(item: dict, reply: dict) -> dict:
    """Compare the reply of the workflow with what the question file expects."""
    answer = str(reply.get("answer", ""))
    sources = [s.get("filename") for s in reply.get("sources", [])]
    refused = REFUSAL in answer.lower()

    if item.get("type") == "refuse":
        return {"refused_ok": refused and not sources}

    patterns = item.get("must_include", [])
    correct = (not refused) and all(re.search(p, answer, re.IGNORECASE) for p in patterns)
    allowed = item.get("expected_files", []) + item.get("cite_also", [])
    cited = any(s in allowed for s in sources) if allowed else bool(sources)
    return {"correct": correct, "cited": cited, "false_refusal": refused}


def percent(count: int, total: int) -> str:
    return f"{count}/{total} ({100 * count / total:.0f}%)" if total else "n/a"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the contract Q&A (workflow C2).")
    parser.add_argument("--retrieval-only", action="store_true", help="skip the language model, test the search only")
    parser.add_argument("--json", metavar="FILE", help="write all results to this JSON file")
    args = parser.parse_args()

    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    env = read_env_file()
    n8n_url = os.environ.get("N8N_URL", "http://localhost:" + env.get("HOST_N8N_PORT", "5678"))
    key = os.environ.get("INTAKE_API_KEY") or env.get("INTAKE_API_KEY", "")
    if not args.retrieval_only and not key:
        print("INTAKE_API_KEY is not set (put it in .env), or use --retrieval-only", file=sys.stderr)
        return 2

    results = []
    try:
        with connect() as conn:
            indexed = conn.execute("SELECT count(*) FROM contract_chunks WHERE embedding IS NOT NULL").fetchone()[0]
            if indexed == 0:
                print("No embedded passages found. Ingest the sample contracts first (workflow C1).", file=sys.stderr)
                return 2
            print(f"{len(questions)} questions, {indexed} embedded passages in the database\n")

            for item in questions:
                result = {"id": item["id"], "question": item["question"]}

                # 1. retrieval (only for questions that name the file holding the answer)
                chunks = search_chunks(conn, embed_question(item["question"]))
                result["top_files"] = [c["filename"] for c in chunks]
                if item.get("expected_files"):
                    result["rank"] = first_correct_rank(chunks, item)

                # 2. the full answer
                if not args.retrieval_only:
                    reply = ask(item["question"], n8n_url, key)
                    result["answer"] = reply.get("answer", reply.get("error"))
                    result["sources"] = [s.get("filename") for s in reply.get("sources", [])]
                    result.update(check_answer(item, reply))

                results.append(result)
                print_line(result, item)
    except (urllib.error.URLError, OSError) as error:
        print(f"\nCould not run: {error}", file=sys.stderr)
        print("Check that Ollama is reachable (set OLLAMA_HOST) and the stack is up.", file=sys.stderr)
        return 2

    return summarise(results, args)


def print_line(result: dict, item: dict) -> None:
    """One line per question: rank of the right passage, then the answer checks."""
    parts = []
    if "rank" in result:
        parts.append(f"rank {result['rank'] or 'MISS'}")
    for name in ("correct", "cited", "refused_ok", "false_refusal"):
        if name in result:
            parts.append(f"{name}={'yes' if result[name] else 'no'}")
    print(f"{result['id']}  {item['question'][:62]:<62}  {'  '.join(parts)}")


def summarise(results: list[dict], args: argparse.Namespace) -> int:
    ranked = [r for r in results if "rank" in r]
    ranks = [r["rank"] for r in ranked]
    print("\n== Retrieval")
    print(f"   questions with a known source: {len(ranked)}")
    for n in (1, 3, 6):
        print(f"   hit@{n}: {percent(sum(1 for r in ranks if r and r <= n), len(ranks))}")
    mrr = sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0
    print(f"   MRR:   {mrr:.2f}")
    misses = [r["id"] for r in ranked if not r["rank"]]
    if misses:
        print(f"   not in the top 6 at all: {', '.join(misses)}")

    problems = 0     # retrieval is reported as numbers; only wrong answers fail the run
    if not args.retrieval_only:
        answerable = [r for r in results if "correct" in r]
        refusals = [r for r in results if "refused_ok" in r]
        print("\n== Answers")
        print(f"   correct facts:   {percent(sum(r['correct'] for r in answerable), len(answerable))}")
        print(f"   cited a source:  {percent(sum(r['cited'] for r in answerable), len(answerable))}")
        print(f"   false refusals:  {percent(sum(r['false_refusal'] for r in answerable), len(answerable))}")
        print(f"   refused out-of-scope: {percent(sum(r['refused_ok'] for r in refusals), len(refusals))}")
        failed = [r["id"] for r in answerable if not (r["correct"] and r["cited"])]
        failed += [r["id"] for r in refusals if not r["refused_ok"]]
        if failed:
            print(f"   to look at: {', '.join(failed)}")
        problems += len(failed)

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nFull results written to {args.json}")
    print("\nAll checks passed." if problems == 0 else f"\n{problems} check(s) failed.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
