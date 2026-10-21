-- Core business data: tools, people, contracts, accounts, usage, budgets.

CREATE TABLE IF NOT EXISTS tools (
    id                  serial PRIMARY KEY,
    name                text NOT NULL UNIQUE,
    vendor              text NOT NULL,
    auth_type           text NOT NULL CHECK (auth_type IN ('api_key', 'oauth2')),
    unit_price_monthly  numeric(10, 2),
    currency            text NOT NULL DEFAULT 'USD'
);

CREATE TABLE IF NOT EXISTS employees (
    id           serial PRIMARY KEY,
    email        text NOT NULL UNIQUE,
    name         text NOT NULL,
    team         text NOT NULL,
    cost_center  text,
    status       text NOT NULL CHECK (status IN ('active', 'terminated')),
    start_date   date,
    end_date     date
);

CREATE TABLE IF NOT EXISTS contracts (
    id                    serial PRIMARY KEY,
    tool_id               integer NOT NULL REFERENCES tools (id),
    contract_ref          text NOT NULL UNIQUE,
    seats                 integer NOT NULL,
    price_per_seat        numeric(10, 2),
    billing_cycle         text,                  -- e.g. monthly, annual
    start_date            date NOT NULL,
    end_date              date NOT NULL,
    notice_days           integer NOT NULL DEFAULT 30,
    auto_renew            boolean NOT NULL DEFAULT false,
    owner_email           text,
    source_document_id    integer                -- set when created from a PDF (FK added in 04-rag.sql)
);

-- Accounts are pulled from the vendor APIs by the workflows, not loaded from seed data.
CREATE TABLE IF NOT EXISTS accounts (
    id              serial PRIMARY KEY,
    tool_id         integer NOT NULL REFERENCES tools (id),
    external_id     text NOT NULL,               -- the vendor's own user id
    email           text,
    seat_type       text,
    status          text,
    created_at      timestamptz,
    last_active_at  timestamptz,
    UNIQUE (tool_id, external_id)
);

CREATE TABLE IF NOT EXISTS usage_daily (
    account_id      integer NOT NULL REFERENCES accounts (id),
    day             date NOT NULL,
    activity_count  integer NOT NULL DEFAULT 0,
    spend_usd       numeric(10, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, day)
);

CREATE TABLE IF NOT EXISTS budgets (
    team     text NOT NULL,
    tool_id  integer NOT NULL REFERENCES tools (id),
    month    date NOT NULL,                      -- first day of the month
    amount   numeric(12, 2) NOT NULL,
    PRIMARY KEY (team, tool_id, month)
);
