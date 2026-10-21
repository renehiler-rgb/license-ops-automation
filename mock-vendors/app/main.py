"""
Mock vendor APIs for the License Ops Automation Suite.

One small FastAPI app that pretends to be five different services:
  - an HR system             GET /hr/employees                      (API key, page numbers)
  - Chatterly AI             GET /v1/chatterly/users|usage          (API key, cursor)
  - DesignHub                GET /v1/designhub/users|usage          (API key, cursor)
  - CodeForge                GET /v2/codeforge/members|activity     (OAuth2, page numbers)
  - MeetSpace                GET /v2/meetspace/members|activity     (OAuth2, page numbers)

Each vendor deliberately uses different field names, date formats and response
shapes. Cleaning that up ("normalising") is the job of the n8n workflows.

The data comes from the JSON files written by scripts/generate_data.py.
Keys and secrets come from environment variables. Some requests fail on
purpose (see CHAOS_RATE) so the workflows have to cope with 429 and 500 errors.
"""

import base64
import json
import os
import random
import secrets
import time
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
TOKEN_LIFETIME_SECONDS = 300
USAGE_PAGE_SIZE = 500          # rows per page for usage / activity
USERS_PAGE_SIZE = 50           # rows per page for users / members

API_KEY_TOOLS = ["chatterly", "designhub"]
OAUTH_TOOLS = ["codeforge", "meetspace"]

app = FastAPI(title="Northwind mock vendor APIs")


# ---------------------------------------------------------------------------
# Configuration and data loading
# ---------------------------------------------------------------------------

def required_env(name: str) -> str:
    """Read a secret from the environment, and stop with a clear message if it is missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set (see .env.example)")
    return value


# API keys: header value expected for each API-key service (the HR system counts as one)
API_KEYS = {
    "hr": required_env("HR_API_KEY"),
    "chatterly": required_env("CHATTERLY_API_KEY"),
    "designhub": required_env("DESIGNHUB_API_KEY"),
}
# OAuth2 client credentials for each OAuth2 tool
OAUTH_CLIENTS = {
    "codeforge": (required_env("CODEFORGE_CLIENT_ID"), required_env("CODEFORGE_CLIENT_SECRET")),
    "meetspace": (required_env("MEETSPACE_CLIENT_ID"), required_env("MEETSPACE_CLIENT_SECRET")),
}


def read_json(name: str) -> list[dict]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


EMPLOYEES = read_json("employees.json")
ACCOUNTS = read_json("accounts.json")
USAGE = read_json("usage.json")

# Group accounts and usage by tool once, at startup
ACCOUNTS_BY_TOOL: dict[str, list[dict]] = {}
for _account in ACCOUNTS:
    ACCOUNTS_BY_TOOL.setdefault(_account["tool"], []).append(_account)

USAGE_BY_TOOL: dict[str, list[dict]] = {}
for _row in sorted(USAGE, key=lambda r: (r["day"], r["external_id"])):
    USAGE_BY_TOOL.setdefault(_row["tool"], []).append(_row)


# ---------------------------------------------------------------------------
# Errors on purpose ("chaos") and authentication
# ---------------------------------------------------------------------------

def maybe_fail(x_chaos: str | None) -> None:
    """With probability CHAOS_RATE, answer with 429 (too many requests) or 500.

    Send the header 'X-Chaos: off' to switch this off, for example when debugging.
    """
    if x_chaos and x_chaos.lower() == "off":
        return
    rate = float(os.environ.get("CHAOS_RATE", "0.05"))
    if random.random() < rate:
        if random.random() < 0.5:
            raise HTTPException(status_code=429, detail="Too many requests",
                                headers={"Retry-After": "2"})
        raise HTTPException(status_code=500, detail="Internal server error (simulated)")


def check_api_key(service: str, x_api_key: str | None) -> None:
    """Stop with 401 unless the X-API-Key header matches this service's key."""
    expected = API_KEYS[service]
    # compare_digest avoids leaking information through timing
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# Issued tokens: token string -> (tool, time it expires)
TOKENS: dict[str, tuple[str, float]] = {}


def check_bearer_token(tool: str, authorization: str | None) -> None:
    """Stop with 401 unless the bearer token is valid, unexpired and issued for this tool."""
    unauthorized = HTTPException(status_code=401, detail="Invalid or expired token",
                                 headers={"WWW-Authenticate": "Bearer"})
    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized
    token = authorization[len("Bearer "):]
    issued = TOKENS.get(token)
    if issued is None or issued[0] != tool or issued[1] < time.time():
        raise unauthorized


@app.post("/oauth/token")
async def oauth_token(request: Request) -> dict:
    """OAuth2 client-credentials flow: exchange client id + secret for a bearer token.

    The credentials are accepted in the form body or in an HTTP Basic header.
    """
    form = await request.form()
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[len("Basic "):]).decode()
            client_id, _, client_secret = decoded.partition(":")
        except ValueError:
            raise HTTPException(status_code=400, detail="Malformed Basic header")

    if form.get("grant_type") != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")

    for tool, (known_id, known_secret) in OAUTH_CLIENTS.items():
        if client_id == known_id and client_secret and \
                secrets.compare_digest(str(client_secret), known_secret):
            token = secrets.token_urlsafe(32)
            TOKENS[token] = (tool, time.time() + TOKEN_LIFETIME_SECONDS)
            return {"access_token": token, "token_type": "Bearer",
                    "expires_in": TOKEN_LIFETIME_SECONDS}
    raise HTTPException(status_code=401, detail="invalid_client")


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------

def cursor_page(rows: list, cursor: str | None, size: int) -> tuple[list, str | None]:
    """Cursor pagination. The cursor is an opaque string that hides a row offset."""
    offset = 0
    if cursor:
        try:
            offset = int(base64.urlsafe_b64decode(cursor.encode()).decode())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor")
    items = rows[offset:offset + size]
    next_offset = offset + size
    next_cursor = None
    if next_offset < len(rows):
        next_cursor = base64.urlsafe_b64encode(str(next_offset).encode()).decode()
    return items, next_cursor


def number_page(rows: list, page: int, size: int) -> tuple[list, int]:
    """Page-number pagination (first page is 1). Returns the items and the total page count."""
    total_pages = max(1, -(-len(rows) // size))      # round up
    start = (page - 1) * size
    return rows[start:start + size], total_pages


def filter_days(rows: list[dict], start: date | None, end: date | None) -> list[dict]:
    """Keep rows whose 'day' lies between start and end (both included, both optional)."""
    result = []
    for row in rows:
        day = date.fromisoformat(row["day"])
        if start and day < start:
            continue
        if end and day > end:
            continue
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Each vendor's own field names and formats
# ---------------------------------------------------------------------------

def epoch_seconds(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())


def chatterly_user(a: dict) -> dict:
    return {"user_id": a["external_id"], "email": a["email"],
            "plan": "pro" if a["seat_type"] == "premium" else "basic",
            "created": epoch_seconds(a["created_at"]),
            "last_seen": epoch_seconds(a["last_active_at"]),
            "state": "active"}


def designhub_user(a: dict) -> dict:
    # DesignHub writes emails in Title Case and dates as "YYYY-MM-DD HH:MM:SS"
    def stamp(iso: str) -> str:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M:%S")
    return {"id": a["external_id"], "email_address": a["email"].title(),
            "role": "creator" if a["seat_type"] == "premium" else "viewer",
            "joined_at": stamp(a["created_at"]),
            "last_login": stamp(a["last_active_at"]),
            "is_active": True}


def codeforge_member(a: dict) -> dict:
    def zulu(iso: str) -> str:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"member_id": a["external_id"], "login": a["email"],
            "license": "enterprise" if a["seat_type"] == "premium" else "team",
            "joined": zulu(a["created_at"]),
            "last_activity": zulu(a["last_active_at"]),
            "suspended": False}


def meetspace_member(a: dict) -> dict:
    return {"uid": a["external_id"], "mail": a["email"],
            "tier": "host" if a["seat_type"] == "premium" else "attendee",
            "created_at": epoch_seconds(a["created_at"]) * 1000,        # milliseconds
            "last_active_at": epoch_seconds(a["last_active_at"]) * 1000,
            "status": "ACTIVE"}


def chatterly_usage(r: dict) -> dict:
    return {"user_id": r["external_id"], "date": r["day"],
            "requests": r["activity_count"], "cost_usd": r["spend_usd"]}


def designhub_usage(r: dict) -> dict:
    return {"id": r["external_id"], "day": r["day"].replace("-", ""),     # 20260105
            "actions": r["activity_count"], "spend_cents": round(r["spend_usd"] * 100)}


def codeforge_activity(r: dict) -> dict:
    return {"member_id": r["external_id"], "date": r["day"],
            "contributions": r["activity_count"]}


def meetspace_activity(r: dict) -> dict:
    day_start = int(datetime.fromisoformat(r["day"]).timestamp())
    return {"uid": r["external_id"], "day_start": day_start, "meetings": r["activity_count"]}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "employees": len(EMPLOYEES), "accounts": len(ACCOUNTS),
            "usage_rows": len(USAGE), "chaos_rate": float(os.environ.get("CHAOS_RATE", "0.05"))}


@app.get("/hr/employees")
def hr_employees(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                 x_api_key: str | None = Header(default=None),
                 x_chaos: str | None = Header(default=None)) -> dict:
    check_api_key("hr", x_api_key)
    maybe_fail(x_chaos)
    items, total_pages = number_page(EMPLOYEES, page, page_size)
    return {
        "page": page, "page_size": page_size, "total": len(EMPLOYEES), "total_pages": total_pages,
        "employees": [{
            "employee_id": f"E{(page - 1) * page_size + i + 1:04d}",
            "email": e["email"], "full_name": e["name"],
            "department": e["team"], "cost_center": e["cost_center"],
            "employment_status": e["status"].upper(),
            "hire_date": e["start_date"], "termination_date": e["end_date"],
        } for i, e in enumerate(items)],
    }


def require_tool(tool: str, allowed: list[str]) -> None:
    if tool not in allowed:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{tool}'")


@app.get("/v1/{tool}/users")
def api_key_users(tool: str, cursor: str | None = None,
                  x_api_key: str | None = Header(default=None),
                  x_chaos: str | None = Header(default=None)) -> dict:
    require_tool(tool, API_KEY_TOOLS)
    check_api_key(tool, x_api_key)
    maybe_fail(x_chaos)
    items, next_cursor = cursor_page(ACCOUNTS_BY_TOOL.get(tool, []), cursor, USERS_PAGE_SIZE)
    if tool == "chatterly":
        return {"data": [chatterly_user(a) for a in items],
                "next_cursor": next_cursor, "has_more": next_cursor is not None}
    return {"items": [designhub_user(a) for a in items], "cursor": {"next": next_cursor}}


@app.get("/v1/{tool}/usage")
def api_key_usage(tool: str, cursor: str | None = None,
                  from_: date | None = Query(None, alias="from"), to: date | None = None,
                  x_api_key: str | None = Header(default=None),
                  x_chaos: str | None = Header(default=None)) -> dict:
    require_tool(tool, API_KEY_TOOLS)
    check_api_key(tool, x_api_key)
    maybe_fail(x_chaos)
    rows = filter_days(USAGE_BY_TOOL.get(tool, []), from_, to)
    items, next_cursor = cursor_page(rows, cursor, USAGE_PAGE_SIZE)
    if tool == "chatterly":
        return {"data": [chatterly_usage(r) for r in items],
                "next_cursor": next_cursor, "has_more": next_cursor is not None}
    return {"items": [designhub_usage(r) for r in items], "cursor": {"next": next_cursor}}


@app.get("/v2/{tool}/members")
def oauth_members(tool: str, page: int = Query(1, ge=1),
                  authorization: str | None = Header(default=None),
                  x_chaos: str | None = Header(default=None)) -> dict:
    require_tool(tool, OAUTH_TOOLS)
    check_bearer_token(tool, authorization)
    maybe_fail(x_chaos)
    items, total_pages = number_page(ACCOUNTS_BY_TOOL.get(tool, []), page, USERS_PAGE_SIZE)
    if tool == "codeforge":
        return {"members": [codeforge_member(a) for a in items],
                "page": page, "per_page": USERS_PAGE_SIZE, "total_pages": total_pages}
    return {"results": [meetspace_member(a) for a in items],
            "page": {"number": page, "size": USERS_PAGE_SIZE,
                     "total_items": len(ACCOUNTS_BY_TOOL.get(tool, []))}}


@app.get("/v2/{tool}/activity")
def oauth_activity(tool: str, page: int = Query(1, ge=1), since: date | None = None,
                   authorization: str | None = Header(default=None),
                   x_chaos: str | None = Header(default=None)) -> dict:
    require_tool(tool, OAUTH_TOOLS)
    check_bearer_token(tool, authorization)
    maybe_fail(x_chaos)
    rows = filter_days(USAGE_BY_TOOL.get(tool, []), since, None)
    items, total_pages = number_page(rows, page, USAGE_PAGE_SIZE)
    if tool == "codeforge":
        return {"events": [codeforge_activity(r) for r in items],
                "page": page, "per_page": USAGE_PAGE_SIZE, "total_pages": total_pages}
    return {"results": [meetspace_activity(r) for r in items],
            "page": {"number": page, "size": USAGE_PAGE_SIZE, "total_items": len(rows)}}
