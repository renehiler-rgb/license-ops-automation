"""
load_data.py - load the generated JSON files into Postgres.

Run it after generate_data.py and after the database is up:
  python3 scripts/load_data.py

It loads tools, employees, contracts and budgets.
Accounts and usage are NOT loaded here: the n8n workflows fetch them
from the mock vendor APIs, which is the whole point of the project.

Every write is an "upsert" (INSERT ... ON CONFLICT DO UPDATE), so running
this script twice gives the same result and never creates duplicates.

Connection settings come from environment variables, falling back to the
values in the .env file in the project root:
  POSTGRES_PASSWORD (required), PGHOST (default localhost), PGPORT (default 5432)
"""

import json
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def read_env_file() -> dict[str, str]:
    """Read KEY=value lines from .env (a very small parser, no extra library)."""
    values = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def read_json(name: str) -> list[dict]:
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def connect() -> psycopg.Connection:
    env = read_env_file()
    password = os.environ.get("POSTGRES_PASSWORD") or env.get("POSTGRES_PASSWORD")
    if not password:
        raise SystemExit("POSTGRES_PASSWORD is not set (put it in .env)")
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname="licenseops",
        user="licenseops",
        password=password,
    )


def load_tools(cur: psycopg.Cursor) -> dict[str, int]:
    """Upsert tools and return a dictionary: slug -> database id."""
    for t in read_json("tools.json"):
        cur.execute(
            """
            INSERT INTO tools (name, vendor, auth_type, unit_price_monthly, currency)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                vendor = EXCLUDED.vendor,
                auth_type = EXCLUDED.auth_type,
                unit_price_monthly = EXCLUDED.unit_price_monthly,
                currency = EXCLUDED.currency
            """,
            (t["name"], t["vendor"], t["auth_type"], t["unit_price_monthly"], t["currency"]),
        )
    cur.execute("SELECT name, id FROM tools")
    id_by_name = dict(cur.fetchall())
    return {t["slug"]: id_by_name[t["name"]] for t in read_json("tools.json")}


def load_employees(cur: psycopg.Cursor) -> int:
    rows = read_json("employees.json")
    for e in rows:
        cur.execute(
            """
            INSERT INTO employees (email, name, team, cost_center, status, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                name = EXCLUDED.name,
                team = EXCLUDED.team,
                cost_center = EXCLUDED.cost_center,
                status = EXCLUDED.status,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date
            """,
            (e["email"], e["name"], e["team"], e["cost_center"], e["status"],
             e["start_date"], e["end_date"]),
        )
    return len(rows)


def load_contracts(cur: psycopg.Cursor, tool_ids: dict[str, int]) -> int:
    rows = read_json("contracts.json")
    for c in rows:
        cur.execute(
            """
            INSERT INTO contracts (tool_id, contract_ref, seats, price_per_seat, billing_cycle,
                                   start_date, end_date, notice_days, auto_renew, owner_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (contract_ref) DO UPDATE SET
                tool_id = EXCLUDED.tool_id,
                seats = EXCLUDED.seats,
                price_per_seat = EXCLUDED.price_per_seat,
                billing_cycle = EXCLUDED.billing_cycle,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                notice_days = EXCLUDED.notice_days,
                auto_renew = EXCLUDED.auto_renew,
                owner_email = EXCLUDED.owner_email
            """,
            (tool_ids[c["tool"]], c["contract_ref"], c["seats"], c["price_per_seat"],
             c["billing_cycle"], c["start_date"], c["end_date"], c["notice_days"],
             c["auto_renew"], c["owner_email"]),
        )
    return len(rows)


def load_budgets(cur: psycopg.Cursor, tool_ids: dict[str, int]) -> int:
    rows = read_json("budgets.json")
    for b in rows:
        cur.execute(
            """
            INSERT INTO budgets (team, tool_id, month, amount)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (team, tool_id, month) DO UPDATE SET amount = EXCLUDED.amount
            """,
            (b["team"], tool_ids[b["tool"]], b["month"], b["amount"]),
        )
    return len(rows)


def main() -> None:
    # "with" commits everything at the end, or rolls back if anything fails
    with connect() as conn:
        with conn.cursor() as cur:
            tool_ids = load_tools(cur)
            print(f"tools:     {len(tool_ids)}")
            print(f"employees: {load_employees(cur)}")
            print(f"contracts: {load_contracts(cur, tool_ids)}")
            print(f"budgets:   {load_budgets(cur, tool_ids)}")


if __name__ == "__main__":
    main()
