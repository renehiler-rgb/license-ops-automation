"""
generate_data.py - synthetic data for the License Ops Automation Suite.

Everything is fictional (company: Northwind Media). Run it with:
  python3 scripts/generate_data.py

It writes JSON files into the data/ folder:
  tools.json, employees.json, contracts.json, budgets.json   (loaded into Postgres by load_data.py)
  accounts.json, usage.json                                   (served by the mock vendor APIs)
  planted_issues.json                                         (the answer key for the audit tests)

The data contains problems on purpose (unused seats, orphaned accounts, ...).
planted_issues.json lists them, so the audit workflow can be checked against it.

The random seed is fixed, so the people and accounts are the same on every run.
Dates are relative to today's date, so the contracts always land on the
90/60/30-day marks no matter when you run the script.
"""

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

rng = random.Random(42)        # our own random generator with a fixed seed
TODAY = date.today()
OUT = Path(__file__).resolve().parent.parent / "data"

WINDOW_DAYS = 120              # how many days of usage history to create
EMPLOYEE_COUNT = 300
TERMINATED_COUNT = 15          # 5% of 300

# How many of each problem to plant
INACTIVE_SEATS = 25
ORPHANS_TERMINATED = 5         # accounts of people who already left
ORPHANS_NOT_IN_HR = 3          # accounts of people HR has never heard of
SEAT_MISMATCHES = 6
DUPLICATES = 3

TEAMS = ["Sales", "BDR", "Marketing", "Engineering", "Design", "Finance", "Ops"]
OVER_BUDGET_TEAMS = ["Sales", "Design"]

# slug is used in URLs and in the other JSON files
TOOLS = [
    {"slug": "chatterly", "name": "Chatterly AI", "vendor": "Chatterly Labs",
     "auth_type": "api_key", "unit_price_monthly": 15.00, "currency": "USD", "prefix": "cht"},
    {"slug": "designhub", "name": "DesignHub", "vendor": "DesignHub Inc.",
     "auth_type": "api_key", "unit_price_monthly": 18.00, "currency": "USD", "prefix": "dsh"},
    {"slug": "codeforge", "name": "CodeForge", "vendor": "CodeForge Systems",
     "auth_type": "oauth2", "unit_price_monthly": 25.00, "currency": "USD", "prefix": "cfg"},
    {"slug": "meetspace", "name": "MeetSpace", "vendor": "MeetSpace Ltd.",
     "auth_type": "oauth2", "unit_price_monthly": 12.00, "currency": "USD", "prefix": "mts"},
]
TOOL_BY_SLUG = {t["slug"]: t for t in TOOLS}

# Chatterly AI is billed by usage on top of the seat price: dollars per activity
CHATTERLY_RATE = 0.04

FIRST_NAMES = [
    "Ana", "Marko", "Jelena", "Nikola", "Ivana", "Stefan", "Milica", "Luka", "Sara", "Petar",
    "Mina", "Filip", "Teodora", "Vuk", "Katarina", "Andrej", "Maja", "Dusan", "Lena", "Viktor",
    "Nina", "Darko", "Irina", "Bojan", "Tamara", "Goran", "Sofija", "Aleksa", "Dunja", "Emil",
]
LAST_NAMES = [
    "Jovanovic", "Petrovic", "Nikolic", "Markovic", "Ilic", "Stojanovic", "Pavlovic", "Kovac",
    "Savic", "Popovic", "Djordjevic", "Todorovic", "Lazic", "Kostic", "Mitic", "Vukovic",
    "Radic", "Simic", "Maric", "Bogdanovic", "Zivkovic", "Tomic", "Babic", "Jankovic",
    "Obradovic", "Milic", "Stanic", "Ristic", "Vasic", "Knezevic",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


def add_months(d: date, n: int) -> date:
    """Return the first day of the month that is n months after d's month."""
    index = d.year * 12 + (d.month - 1) + n
    return date(index // 12, index % 12 + 1, 1)


def normalise_email(email: str) -> str:
    """Lower-case an email and drop any +tag (ana+alias@x -> ana@x)."""
    local_part, domain = email.lower().split("@")
    return local_part.split("+")[0] + "@" + domain


def timestamp(day: date, hour: int) -> str:
    """Format a date plus an hour as an ISO timestamp (UTC)."""
    return f"{day.isoformat()}T{hour:02d}:{rng.randint(0, 59):02d}:00+00:00"


def save(name: str, data) -> None:
    """Write data to data/<name> as JSON."""
    OUT.mkdir(exist_ok=True)
    with open(OUT / name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1 if len(str(data)) < 20000 else None)
    count = len(data) if isinstance(data, list) else "-"
    print(f"wrote {count:>6} rows -> data/{name}")


# ---------------------------------------------------------------------------
# Step 1: employees
# ---------------------------------------------------------------------------

def make_employees() -> list[dict]:
    """300 employees; the last 15 have left the company in the last 90 days."""
    # Every first/last name pair is used at most once, so every email is unique.
    pairs = [(f, l) for f in FIRST_NAMES for l in LAST_NAMES]
    rng.shuffle(pairs)

    employees = []
    for number in range(EMPLOYEE_COUNT):
        first, last = pairs[number]
        team = rng.choice(TEAMS)
        terminated = number >= EMPLOYEE_COUNT - TERMINATED_COUNT
        if terminated:
            start = days_ago(rng.randint(120, 1400))
            end = days_ago(rng.randint(1, 90))
        else:
            start = days_ago(rng.randint(30, 1500))
            end = None
        employees.append({
            "email": f"{first.lower()}.{last.lower()}@northwind.example",
            "name": f"{first} {last}",
            "team": team,
            "cost_center": f"CC-{team.upper()}",
            "status": "terminated" if terminated else "active",
            "start_date": start.isoformat(),
            "end_date": end.isoformat() if end else None,
        })
    return employees


# ---------------------------------------------------------------------------
# Step 2: accounts (who has which tool), with the planted problems
# ---------------------------------------------------------------------------
# While we build accounts we keep a few extra fields that start with "_".
# They are used to create the usage data and are removed before saving.

class AccountFactory:
    """Creates accounts and gives each one a vendor-style external id."""

    def __init__(self) -> None:
        self.counters = {t["slug"]: 0 for t in TOOLS}

    def create(self, tool: str, email: str, earliest: date, latest: date) -> dict:
        self.counters[tool] += 1
        prefix = TOOL_BY_SLUG[tool]["prefix"]
        # created_at falls somewhere between the two dates (at most 60 days after 'earliest')
        span = max(0, min(60, (latest - earliest).days))
        created = earliest + timedelta(days=rng.randint(0, span))
        return {
            "tool": tool,
            "external_id": f"{prefix}_{self.counters[tool]:05d}",
            "email": email,
            "seat_type": "standard",
            "status": "active",
            "created_at": created,                 # a date for now, turned into text later
            "_profile": "normal",                  # heavy / normal / light
            "_last_day": TODAY - timedelta(days=1),   # last day this account can have usage
            "_light_days": [],
            "_employee": None,
            "_kind": "regular",
        }


def make_accounts(employees: list[dict]) -> tuple[list[dict], dict]:
    """Build all accounts and pick the ones that carry a planted problem."""
    factory = AccountFactory()
    accounts = []
    tool_slugs = [t["slug"] for t in TOOLS]

    active = [e for e in employees if e["status"] == "active"]
    terminated = [e for e in employees if e["status"] == "terminated"]

    # --- Regular accounts: most active employees get 1-3 tools -------------
    for emp in active:
        how_many = rng.choices([1, 2, 3], weights=[40, 40, 20])[0]
        for tool in rng.sample(tool_slugs, how_many):
            account = factory.create(tool, emp["email"],
                                     date.fromisoformat(emp["start_date"]), days_ago(1))
            account["_employee"] = emp
            # Heavy users sometimes have a premium seat; everyone else is standard
            if rng.random() < 0.35:
                account["_profile"] = "heavy"
                if rng.random() < 0.4:
                    account["seat_type"] = "premium"
            accounts.append(account)

    # --- Orphans, part 1: people who left but still have an account --------
    # They left in the last 29 days, so they do not also count as "inactive 30+ days".
    leavers = terminated[:ORPHANS_TERMINATED]
    for emp in leavers:
        emp["end_date"] = days_ago(rng.randint(1, 29)).isoformat()
        end = date.fromisoformat(emp["end_date"])
        account = factory.create(rng.choice(tool_slugs), emp["email"],
                                 date.fromisoformat(emp["start_date"]), end - timedelta(days=1))
        account["_employee"] = emp
        account["_last_day"] = end                 # usage stops the day they leave
        account["_kind"] = "orphan"
        accounts.append(account)

    # --- Orphans, part 2: accounts for people who are not in HR at all -----
    used_names = {e["name"] for e in employees}
    stranger_count = 0
    while stranger_count < ORPHANS_NOT_IN_HR:
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        if f"{first} {last}" in used_names:
            continue
        used_names.add(f"{first} {last}")
        email = f"contractor.{first.lower()}.{last.lower()}@northwind.example"
        account = factory.create(rng.choice(tool_slugs), email, days_ago(400), days_ago(60))
        account["_kind"] = "orphan"
        accounts.append(account)
        stranger_count += 1

    # --- Pick accounts for the other planted problems ----------------------
    # Each account is used for at most one problem, so the answer key stays clean.
    pool = [a for a in accounts if a["_kind"] == "regular"]
    rng.shuffle(pool)
    inactive = pool[:INACTIVE_SEATS]
    mismatched = pool[INACTIVE_SEATS:INACTIVE_SEATS + SEAT_MISMATCHES]
    duplicated = pool[INACTIVE_SEATS + SEAT_MISMATCHES:
                      INACTIVE_SEATS + SEAT_MISMATCHES + DUPLICATES]

    # 25 inactive seats: last activity between 31 and 110 days ago, standard seat
    for account in inactive:
        account["_kind"] = "inactive"
        account["_profile"] = "normal"
        account["seat_type"] = "standard"
        account["_last_day"] = days_ago(rng.randint(31, 110))
        # the account must exist before its last activity
        latest_created = account["_last_day"] - timedelta(days=3)
        account["created_at"] = min(account["created_at"], latest_created)

    # 6 seat mismatches: premium seat, but only 1-4 active days in the last 30
    for account in mismatched:
        account["_kind"] = "mismatch"
        account["_profile"] = "light"
        account["seat_type"] = "premium"
        recent = [days_ago(n) for n in range(1, 31) if days_ago(n).weekday() < 5]
        picked = rng.sample(recent, rng.randint(1, 4))
        picked.append(days_ago(rng.randint(1, 10)))        # make sure they were seen recently
        account["_light_days"] = sorted(set(picked))

    # 3 duplicates: the same person has a second account in the same tool,
    # under a plus-alias of their email (ana.nikolic+alias@...).
    for account in duplicated:
        account["_kind"] = "duplicate"
        emp = account["_employee"]
        local_part, domain = emp["email"].split("@")
        alias = f"{local_part}+alias@{domain}"
        second = factory.create(account["tool"], alias,
                                date.fromisoformat(emp["start_date"]), days_ago(1))
        second["_employee"] = emp
        second["_kind"] = "duplicate"
        accounts.append(second)

    # --- The answer key ----------------------------------------------------
    def ref(a: dict) -> dict:
        return {"tool": a["tool"], "external_id": a["external_id"], "email": a["email"]}

    planted = {
        "inactive_seats": [dict(ref(a), last_active=a["_last_day"].isoformat()) for a in inactive],
        "orphaned_accounts": [
            dict(ref(a), reason="terminated" if a["_employee"] else "not_in_hr")
            for a in accounts if a["_kind"] == "orphan"
        ],
        "seat_type_mismatches": [ref(a) for a in mismatched],
        "duplicate_accounts": [],
    }
    for original in duplicated:
        both = [a for a in accounts
                if a["_kind"] == "duplicate" and a["tool"] == original["tool"]
                and a["_employee"] is original["_employee"]]
        planted["duplicate_accounts"].append({
            "tool": original["tool"],
            "employee_email": original["_employee"]["email"],
            "accounts": [ref(a) for a in both],
        })
    return accounts, planted


# ---------------------------------------------------------------------------
# Step 3: daily usage for every account
# ---------------------------------------------------------------------------

# profile -> (chance of activity on a weekday, range of activity counts)
PROFILES = {
    "heavy": (0.95, (20, 60)),
    "normal": (0.80, (5, 25)),
    "light": (0.0, (1, 3)),     # light accounts use fixed days instead (_light_days)
}


def make_usage(accounts: list[dict]) -> list[dict]:
    """Create usage rows for the last 120 days and fill in each account's last_active_at."""
    usage = []
    first_window_day = days_ago(WINDOW_DAYS)

    for account in accounts:
        chance, (low, high) = PROFILES[account["_profile"]]
        start = max(account["created_at"], first_window_day)
        end = account["_last_day"]
        active_days = []

        if account["_profile"] == "light":
            active_days = [d for d in account["_light_days"] if start <= d <= end]
        else:
            day = start
            while day <= end:
                is_weekend = day.weekday() >= 5
                # weekends are quiet: one tenth of the weekday chance
                if rng.random() < (chance * 0.1 if is_weekend else chance):
                    active_days.append(day)
                day += timedelta(days=1)

            # Everything except inactive seats and leavers should look recently active
            if account["_kind"] in ("regular", "duplicate", "mismatch") or \
                    (account["_kind"] == "orphan" and not account["_employee"]):
                recent = [d for d in active_days if (TODAY - d).days <= 10]
                if not recent:
                    active_days.append(max(start, days_ago(rng.randint(1, 3))))

            # Inactive seats must end exactly on their last day
            if account["_kind"] == "inactive" and end not in active_days:
                active_days.append(end)

        for day in sorted(set(active_days)):
            count = rng.randint(low, high)
            spend = round(count * CHATTERLY_RATE, 2) if account["tool"] == "chatterly" else 0.0
            usage.append({
                "tool": account["tool"],
                "external_id": account["external_id"],
                "day": day.isoformat(),
                "activity_count": count,
                "spend_usd": spend,
            })

        last_active = max(active_days) if active_days else account["created_at"]
        account["_last_active"] = last_active
    return usage


def finish_accounts(accounts: list[dict]) -> list[dict]:
    """Turn dates into text and drop the helper fields that start with '_'."""
    result = []
    for a in accounts:
        row = {k: v for k, v in a.items() if not k.startswith("_")}
        row["created_at"] = timestamp(a["created_at"], 9)
        row["last_active_at"] = timestamp(a["_last_active"], 15)
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Step 4: contracts and budgets
# ---------------------------------------------------------------------------

def make_contracts(accounts: list[dict]) -> tuple[list[dict], list[dict]]:
    """One contract per tool plus 2 add-ons. Three land on the 90/60/30-day notice marks."""
    seats_needed = {t["slug"]: 0 for t in TOOLS}
    for a in accounts:
        seats_needed[a["tool"]] += 1

    # (tool, reference, title, notice_days, forced days until the notice deadline)
    plan = [
        ("chatterly", "NW-CHT-001", "main", 30, 90),
        ("designhub", "NW-DSH-001", "main", 60, None),
        ("codeforge", "NW-CFG-001", "main", 30, 60),
        ("meetspace", "NW-MTS-001", "main", 90, None),
        ("designhub", "NW-DSH-002", "brand kit add-on", 30, 30),
        ("codeforge", "NW-CFG-002", "security add-on", 60, None),
    ]

    contracts = []
    marks = []
    for tool, ref, title, notice, forced in plan:
        price = TOOL_BY_SLUG[tool]["unit_price_monthly"]
        if forced is not None:
            deadline_in = forced
        else:
            # far from any alert mark, but not so far that the contract (one year long)
            # would only start in the future
            deadline_in = rng.randint(130, 250)
        end = TODAY + timedelta(days=deadline_in + notice)
        if title == "main":
            seats = math.ceil(seats_needed[tool] * 1.15)    # 15% spare seats
        else:
            seats = 20 if "brand" in title else 30
        contracts.append({
            "tool": tool,
            "contract_ref": ref,
            "seats": seats,
            "price_per_seat": price,
            "billing_cycle": rng.choice(["annual", "monthly"]),
            "start_date": (end - timedelta(days=365)).isoformat(),
            "end_date": end.isoformat(),
            "notice_days": notice,
            "auto_renew": rng.random() < 0.5,
            "owner_email": "it-licensing@northwind.example",
        })
        if forced is not None:
            marks.append({"contract_ref": ref, "days_until_notice_deadline": forced})
    return contracts, marks


def make_budgets(accounts: list[dict], usage: list[dict], employees: list[dict]) -> list[dict]:
    """Monthly budget per team and tool for the last 4 months plus the current one.

    The expected monthly cost is seat cost + average Chatterly usage spend.
    Normal teams get a budget 25-45% above that. The OVER_BUDGET_TEAMS get 50% below,
    so they are over budget in every month.
    """
    team_of = {e["email"]: e["team"] for e in employees}
    account_team = {}
    seat_count = {}                      # (team, tool) -> number of accounts
    for a in accounts:
        team = team_of.get(normalise_email(a["email"]))
        if team is None:
            continue                     # not in HR: no team, no budget
        account_team[(a["tool"], a["external_id"])] = team
        key = (team, a["tool"])
        seat_count[key] = seat_count.get(key, 0) + 1

    usage_spend = {}                     # (team, tool) -> total spend over the window
    for row in usage:
        team = account_team.get((row["tool"], row["external_id"]))
        if team:
            key = (team, row["tool"])
            usage_spend[key] = usage_spend.get(key, 0.0) + row["spend_usd"]

    months = [add_months(TODAY, -n) for n in range(4, -1, -1)]    # oldest first
    budgets = []
    for team in TEAMS:
        for tool in TOOLS:
            key = (team, tool["slug"])
            seats = seat_count.get(key, 0)
            expected = seats * tool["unit_price_monthly"]
            expected += usage_spend.get(key, 0.0) / WINDOW_DAYS * 30
            if expected == 0:
                continue
            factor = 0.5 if team in OVER_BUDGET_TEAMS else rng.uniform(1.25, 1.45)
            amount = round(expected * factor / 10) * 10
            for month in months:
                budgets.append({
                    "team": team,
                    "tool": tool["slug"],
                    "month": month.isoformat(),
                    "amount": max(amount, 10),
                })
    return budgets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    employees = make_employees()
    accounts, planted = make_accounts(employees)
    usage = make_usage(accounts)
    contracts, renewal_marks = make_contracts(accounts)
    budgets = make_budgets(accounts, usage, employees)
    accounts_out = finish_accounts(accounts)

    planted["renewal_marks"] = renewal_marks
    planted["over_budget_teams"] = OVER_BUDGET_TEAMS
    planted["notes"] = {
        "generated_on": TODAY.isoformat(),
        "inactive_seats": "active employee, no activity for 30+ days",
        "orphaned_accounts": "employee terminated, or email not in HR",
        "seat_type_mismatches": "premium seat but at most 5 active days in the last 30",
        "duplicate_accounts": "two accounts in one tool for the same employee; the second "
                              "uses a +alias email",
        "email_matching": "compare emails in lower case with any +tag removed "
                          "(ana.nikolic+alias@x -> ana.nikolic@x); the alias accounts are "
                          "duplicates, not orphans",
        "over_budget_teams": "actual monthly cost is above budget for every month and tool",
    }

    # tools.json: drop the helper 'prefix' field
    tools_out = [{k: v for k, v in t.items() if k != "prefix"} for t in TOOLS]

    save("tools.json", tools_out)
    save("employees.json", employees)
    save("contracts.json", contracts)
    save("budgets.json", budgets)
    save("accounts.json", accounts_out)
    save("usage.json", usage)
    save("planted_issues.json", planted)

    print(f"\n{len(employees)} employees, {len(accounts_out)} accounts, {len(usage)} usage rows")
    print(f"planted: {len(planted['inactive_seats'])} inactive, "
          f"{len(planted['orphaned_accounts'])} orphaned, "
          f"{len(planted['seat_type_mismatches'])} mismatches, "
          f"{len(planted['duplicate_accounts'])} duplicates")


if __name__ == "__main__":
    main()
