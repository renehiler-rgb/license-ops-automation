"""
generate_data.py - synthetic data for the License Ops Automation Suite.

Writes four CSV files into a data/ folder:
  software_catalogue.csv, contracts.csv, users_assignments.csv, hiring_forecast.csv

Everything is fictional (company: Northwind Media). Run it with:
  python3 scripts/generate_data.py

Python ideas used here, in order of appearance: imports, constants, lists,
dictionaries, functions, loops, random choices, dates, and writing CSV files.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)          # same "random" data every run, so tests are repeatable
TODAY = date.today()
OUT = Path(__file__).resolve().parent.parent / "data"

TEAMS = ["Sales", "Marketing", "Finance", "Engineering", "Customer Success", "HR"]
ROLES = {                       # role -> team it belongs to
    "Account Executive": "Sales",
    "SDR": "Sales",
    "Content Marketer": "Marketing",
    "Financial Analyst": "Finance",
    "Software Engineer": "Engineering",
    "CS Manager": "Customer Success",
    "HR Partner": "HR",
}

# product_id, name, vendor, license type, EUR per seat per month, roles that need it
CATALOGUE = [
    ("P01", "Salesforce Sales Cloud", "Salesforce", "per seat", 140, ["Account Executive", "SDR"]),
    ("P02", "LinkedIn Sales Navigator", "LinkedIn", "per seat", 90, ["Account Executive", "SDR"]),
    ("P03", "Gong", "Gong", "per seat", 110, ["Account Executive"]),
    ("P04", "HubSpot Marketing Hub", "HubSpot", "per seat", 75, ["Content Marketer"]),
    ("P05", "Canva Teams", "Canva", "per seat", 12, ["Content Marketer", "HR Partner"]),
    ("P06", "Jira Software", "Atlassian", "per seat", 8, ["Software Engineer", "Financial Analyst"]),
    ("P07", "GitHub Enterprise", "GitHub", "per seat", 20, ["Software Engineer"]),
    ("P08", "Zendesk Suite", "Zendesk", "per seat", 85, ["CS Manager"]),
    ("P09", "Claude Team", "Anthropic", "per seat", 28, list(ROLES)),
    ("P10", "Slack Business+", "Slack", "per seat", 12, list(ROLES)),
]

FIRST = ["Ana", "Marko", "Jelena", "Nikola", "Ivana", "Stefan", "Milica", "Luka", "Sara", "Petar"]
LAST = ["Jovanovic", "Petrovic", "Nikolic", "Markovic", "Ilic", "Stojanovic", "Pavlovic", "Kovac"]


def write_csv(name, header, rows):
    """Write a list of rows to data/<name> with a header line."""
    OUT.mkdir(exist_ok=True)
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {len(rows):>4} rows -> data/{name}")


def make_catalogue():
    rows = []
    for pid, name, vendor, ltype, cost, roles in CATALOGUE:
        rows.append([pid, name, vendor, ltype, cost, "it-licensing@northwind.example", "; ".join(roles)])
    write_csv("software_catalogue.csv",
              ["product_id", "name", "vendor", "license_type", "unit_cost_eur_month", "owner", "roles"], rows)


def make_contracts():
    """One contract per product. Three of them land exactly on the 90/60/30-day alert marks."""
    rows = []
    forced = {"P01": 90, "P04": 60, "P08": 30}          # days until notice deadline
    for i, (pid, name, vendor, _, cost, _) in enumerate(CATALOGUE, start=1):
        notice = random.choice([30, 60, 90])
        if pid in forced:
            renewal = TODAY + timedelta(days=forced[pid] + notice)
        else:
            renewal = TODAY + timedelta(days=random.randint(120, 400))
        seats = random.randint(20, 150)
        rows.append([f"C{i:03d}", pid, seats, renewal.isoformat(), notice,
                     seats * cost * 12, f"{vendor.lower()}-owner@northwind.example"])
    write_csv("contracts.csv",
              ["contract_id", "product_id", "seats", "renewal_date", "notice_days",
               "annual_value_eur", "owner_email"], rows)


def make_users(count=300):
    """Users with their product assignments. About 15% have not been active for 30+ days."""
    rows = []
    for n in range(1, count + 1):
        role = random.choice(list(ROLES))
        email = f"{random.choice(FIRST).lower()}.{random.choice(LAST).lower()}{n}@northwind.example"
        for pid, _, _, _, _, roles in CATALOGUE:
            if role in roles:
                assigned = TODAY - timedelta(days=random.randint(30, 700))
                inactive = random.random() < 0.15
                last_active = TODAY - timedelta(days=random.randint(31, 120) if inactive else random.randint(0, 10))
                rows.append([email, ROLES[role], role, pid, assigned.isoformat(),
                             last_active.isoformat(), "active"])
    write_csv("users_assignments.csv",
              ["user_email", "team", "role", "product_id", "assigned_date", "last_active_date", "status"], rows)


def make_forecast():
    """Next month's hiring forecast: what the monthly email would contain."""
    first_next = (TODAY.replace(day=1) + timedelta(days=32)).replace(day=1)
    rows = [[first_next.strftime("%Y-%m"), team, role, random.randint(0, 6)] for role, team in ROLES.items()]
    write_csv("hiring_forecast.csv", ["month", "team", "role", "headcount"], rows)


if __name__ == "__main__":
    make_catalogue()
    make_contracts()
    make_users()
    make_forecast()
    print("done: import each CSV as its own tab in one Google Sheet, plus an empty 'Run Log' tab")
