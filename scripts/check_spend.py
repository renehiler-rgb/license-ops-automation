"""
check_spend.py - check the spend numbers of workflow B against the generated data.

Run it after the reports exist (workflow B stored them in monthly_reports):
  python3 scripts/check_spend.py                # months 2026-07 2026-08 2026-09
  python3 scripts/check_spend.py 2026-08        # one or more months

It recomputes everything straight from data/*.json, WITHOUT using the SQL views, and compares:
  1. every team + tool: actual and budget against the view v_budget_variance
  2. the stored report (monthly_reports.totals): overall actual and budget
  3. the planted over-budget teams (planted_issues.json) show up as over budget in the report

The rules it follows (same as db/init/06-finance-views.sql):
  committed = contract seats x price per seat, prorated by the days the contract is in force
              in the month, shared between teams by their number of accounts that month
  actual    = committed + metered usage spend
Exit code 0 = everything matches, 1 = at least one difference.
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_data import DATA, connect  # noqa: E402

DEFAULT_MONTHS = ["2026-07", "2026-08", "2026-09"]
TOLERANCE = 0.05   # money may differ by a few cents because the database rounds


def read(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def canonical(email: str) -> str:
    """Lower-case and drop a '+tag' (ana+alias@x -> ana@x), the same rule the audit uses."""
    return re.sub(r"\+[^@]*@", "@", email.strip().lower())


def month_bounds(month: str) -> tuple[date, date]:
    """'2026-09' -> (2026-09-01, 2026-10-01): first day of the month and of the next one."""
    year, mon = int(month[:4]), int(month[5:7])
    start = date(year, mon, 1)
    end = date(year + (mon == 12), mon % 12 + 1, 1)
    return start, end


def committed_for_month(contracts: list[dict], tool: str, start: date, end: date) -> float:
    """Contract cost of one tool in one month, prorated by the days the contract is in force."""
    days_in_month = (end - start).days
    total = 0.0
    for c in contracts:
        if c["tool"] != tool:
            continue
        first = max(date.fromisoformat(c["start_date"]), start)
        last = min(date.fromisoformat(c["end_date"]), end - timedelta(days=1))   # end date counts as in force
        days = (last - first).days + 1
        if days > 0:
            total += c["seats"] * c["price_per_seat"] * days / days_in_month
    return total


def expected_rows(month: str) -> dict[tuple[str, str], dict]:
    """Return {(team, tool): {"actual": ..., "budget": ...}} for one month, computed from the JSON files."""
    start, end = month_bounds(month)
    contracts = read("contracts.json")
    team_of = {e["email"]: e["team"] for e in read("employees.json")}

    # which team does each account belong to, and did it exist during this month?
    account_team: dict[tuple[str, str], str] = {}
    accounts_per: dict[tuple[str, str], int] = {}        # (tool, team) -> accounts that month
    for a in read("accounts.json"):
        team = team_of.get(canonical(a["email"]), "Unknown")
        account_team[(a["tool"], a["external_id"])] = team
        if date.fromisoformat(a["created_at"][:10]) < end:
            accounts_per[(a["tool"], team)] = accounts_per.get((a["tool"], team), 0) + 1

    # metered usage spend in the month per (tool, team)
    usage_spend: dict[tuple[str, str], float] = {}
    for u in read("usage.json"):
        if not (start <= date.fromisoformat(u["day"]) < end):
            continue
        key = (u["tool"], account_team[(u["tool"], u["external_id"])])
        usage_spend[key] = usage_spend.get(key, 0.0) + u["spend_usd"]

    budgets = {(b["team"], b["tool"]): b["amount"] for b in read("budgets.json") if b["month"] == start.isoformat()}

    rows: dict[tuple[str, str], dict] = {}
    for tool in {t for t, _ in accounts_per}:
        committed = committed_for_month(contracts, tool, start, end)
        total_accounts = sum(n for (t, _), n in accounts_per.items() if t == tool)
        for (t, team), n in accounts_per.items():
            if t != tool:
                continue
            actual = committed * n / total_accounts + usage_spend.get((tool, team), 0.0)
            rows[(team, tool)] = {"actual": actual, "budget": budgets.get((team, tool))}
    return rows


def close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= TOLERANCE


def main() -> int:
    months = sys.argv[1:] or DEFAULT_MONTHS
    planted = read("planted_issues.json")["over_budget_teams"]
    problems = 0

    with connect() as conn:
        for month in months:
            expected = expected_rows(month)
            print(f"== {month}")

            # 1. team + tool rows from the view
            view = conn.execute(
                """SELECT team, lower(split_part(tool, ' ', 1)), actual, budget
                   FROM v_budget_variance WHERE month = %s""",
                (month + "-01",),
            ).fetchall()
            got = {(team, tool): {"actual": actual, "budget": budget} for team, tool, actual, budget in view}
            wrong = [k for k in expected if k not in got
                     or not close(got[k]["actual"], expected[k]["actual"])
                     or not close(got[k]["budget"], expected[k]["budget"])]
            missing = [k for k in got if k not in expected]
            print(f"   team+tool rows: {len(expected)} expected, {len(got)} in the view, "
                  f"{len(wrong)} wrong, {len(missing)} unexpected")
            for k in wrong[:5]:
                print(f"     WRONG {k}: expected {expected[k]}, view has {got.get(k)}")
            problems += len(wrong) + len(missing)

            # 2. stored report
            report = conn.execute("SELECT totals FROM monthly_reports WHERE month = %s", (month + "-01",)).fetchone()
            if report is None:
                print("   report: NOT STORED (run workflow B for this month)")
                problems += 1
                continue
            totals = report[0]
            want_actual = sum(r["actual"] for r in expected.values())
            want_budget = sum(r["budget"] for r in expected.values() if r["budget"] is not None)
            overall = totals["overall"]
            ok = close(overall["actual"], want_actual) and close(overall["budget"], want_budget)
            print(f"   report totals: actual {overall['actual']} (expected {want_actual:.2f}), "
                  f"budget {overall['budget']} (expected {want_budget:.2f}) -> {'OK' if ok else 'WRONG'}")
            problems += 0 if ok else 1

            # 3. planted over-budget teams
            over = {t["team"] for t in totals["teams_over_budget"]}
            in_top = {r["team"] for r in totals["top_variances"]}
            missing_teams = [t for t in planted if t not in over]
            print(f"   planted over-budget teams {planted}: flagged {sorted(over & set(planted))}, "
                  f"in top 3 variances {sorted(in_top & set(planted))}"
                  f"{'' if not missing_teams else '  MISSING ' + str(missing_teams)}")
            problems += len(missing_teams)
            if not in_top & set(planted):
                print("     no planted team in the top 3 variances")
                problems += 1

    print()
    print("OK: all numbers match." if problems == 0 else f"{problems} difference(s) found.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
