"""
check_audit.py - compare what Workflow A found with the issues planted in the data.

Run it after Workflow A has run:
  python3 scripts/check_audit.py

For each kind of issue it prints:
  found   - planted AND flagged by the audit (good)
  missed  - planted but NOT flagged (a gap in the audit rules)
  extra   - flagged but NOT planted (a false positive, or a real issue the generator did not plant)

The exit code is 0 when nothing was missed and nothing extra was found, otherwise 1.
Only findings that are still open (not resolved) are compared.

Connection settings are the same as load_data.py: POSTGRES_PASSWORD from the environment
or .env, PGHOST (default localhost), PGPORT (default 5432).
"""

import json
import sys
from pathlib import Path

# load_data.py sits next to this file; reuse its connect() so the settings live in one place
sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_data import DATA, connect  # noqa: E402

# One account is identified by (tool, external_id), for example ("chatterly", "cht_00016").
AccountKey = tuple[str, str]


def planted_accounts(planted: dict) -> dict[str, set[AccountKey]]:
    """Turn planted_issues.json into one set of (tool, external_id) per finding type."""
    result: dict[str, set[AccountKey]] = {
        "inactive_seat": {(i["tool"], i["external_id"]) for i in planted["inactive_seats"]},
        "orphaned_account": {(i["tool"], i["external_id"]) for i in planted["orphaned_accounts"]},
        "seat_mismatch": {(i["tool"], i["external_id"]) for i in planted["seat_type_mismatches"]},
        # A planted duplicate lists two accounts; the audit flags the second (the "+alias" one).
        "duplicate_account": {
            (d["tool"], d["accounts"][1]["external_id"]) for d in planted["duplicate_accounts"]
        },
    }
    return result


def found_accounts(conn) -> dict[str, set[AccountKey]]:
    """Read the open findings from the database as (tool, external_id) per finding type."""
    sql = """
        SELECT f.finding_type, lower(split_part(t.name, ' ', 1)), a.external_id
        FROM audit_findings f
        JOIN accounts a ON a.id = f.account_id
        JOIN tools t    ON t.id = a.tool_id
        WHERE f.resolved_at IS NULL
    """
    result: dict[str, set[AccountKey]] = {}
    with conn.cursor() as cur:
        cur.execute(sql)
        for finding_type, tool, external_id in cur.fetchall():
            result.setdefault(finding_type, set()).add((tool, external_id))
        # Findings that are not about one account (over_allocation) are shown but not compared.
        cur.execute(
            "SELECT finding_type, count(*) FROM audit_findings "
            "WHERE resolved_at IS NULL AND account_id IS NULL GROUP BY finding_type"
        )
        for finding_type, count in cur.fetchall():
            print(f"note: {count} open '{finding_type}' finding(s) are not tied to one account (not compared)")
    return result


def main() -> int:
    with open(DATA / "planted_issues.json", encoding="utf-8") as f:
        planted = planted_accounts(json.load(f))

    with connect() as conn:
        found = found_accounts(conn)

    problems = 0
    print(f"{'finding type':<20}{'planted':>8}{'found':>8}{'missed':>8}{'extra':>8}")
    for finding_type, expected in planted.items():
        actual = found.get(finding_type, set())
        hit = expected & actual
        missed = expected - actual
        extra = actual - expected
        problems += len(missed) + len(extra)
        print(f"{finding_type:<20}{len(expected):>8}{len(hit):>8}{len(missed):>8}{len(extra):>8}")
        for tool, external_id in sorted(missed):
            print(f"    MISSED  {tool} {external_id}")
        for tool, external_id in sorted(extra):
            print(f"    EXTRA   {tool} {external_id}")

    # Finding types the generator never plants (so every one of them counts as "extra")
    for finding_type in sorted(set(found) - set(planted)):
        print(f"{finding_type:<20}{'-':>8}{len(found[finding_type]):>8}   (not planted, not compared)")

    print("\nOK: every planted issue was found, nothing extra." if problems == 0
          else f"\n{problems} difference(s) found.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
