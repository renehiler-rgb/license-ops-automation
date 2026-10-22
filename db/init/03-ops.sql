-- Operational tables: config, run log, findings, dead letters, alerts, reports.

CREATE TABLE IF NOT EXISTS app_config (
    key         text PRIMARY KEY,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Seed values. DO NOTHING keeps any value you changed later.
INSERT INTO app_config (key, value) VALUES
    ('jira_enabled',          'false'::jsonb),
    ('llm_provider',          '"anthropic"'::jsonb),
    ('anthropic_model',       '"claude-haiku-5-5"'::jsonb),
    ('inactive_days',         '30'::jsonb),
    ('renewal_thresholds',    '[90, 60, 30]'::jsonb),
    ('slack_channel_alerts',  '"#automation-alerts"'::jsonb),
    ('slack_channel_reports', '"#license-reports"'::jsonb),
    -- Workflow A (usage audit)
    ('usage_initial_days',        '120'::jsonb),   -- first sync: how far back to pull usage
    ('new_account_grace_days',    '14'::jsonb),    -- accounts younger than this are never "inactive"
    ('mismatch_window_days',      '30'::jsonb),    -- window for the premium-seat check
    ('mismatch_min_avg_activity', '3'::jsonb),     -- premium seat below this daily average is a mismatch
    ('post_empty_digest',         'false'::jsonb), -- post a "no new findings" line to Slack
    -- Workflow B (spend report): local model for the summary
    ('ollama_url',                '"http://host.docker.internal:11434"'::jsonb),
    ('ollama_summary_model',      '"llama3.1:8b"'::jsonb),
    -- Workflow D (renewal alerts); Jira stays off until jira_enabled is true and these three are filled in
    ('slack_channel_renewals',    '"#license-reports"'::jsonb),
    ('jira_base_url',             '""'::jsonb),            -- e.g. https://yourcompany.atlassian.net
    ('jira_project_key',          '""'::jsonb),            -- e.g. LIC
    ('jira_issue_type',           '"Task"'::jsonb),
    -- Workflow C (contract intake and questions): local models used for embeddings and the Ollama fallback
    ('ollama_embed_model',        '"nomic-embed-text"'::jsonb),
    ('ollama_extract_model',      '"llama3.1:8b"'::jsonb)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS workflow_runs (
    id            serial PRIMARY KEY,
    workflow      text NOT NULL,
    execution_id  text,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text,
    items_in      integer,
    items_out     integer,
    notes         text
);

CREATE TABLE IF NOT EXISTS audit_findings (
    id             serial PRIMARY KEY,
    finding_type   text NOT NULL,
    account_id     integer REFERENCES accounts (id),
    employee_email text,
    severity       text,
    details        jsonb,
    first_seen     timestamptz NOT NULL DEFAULT now(),
    last_seen      timestamptz NOT NULL DEFAULT now(),
    resolved_at    timestamptz,
    notified_at    timestamptz
);

-- One row per finding. NULLs never match in a normal UNIQUE constraint,
-- so COALESCE turns them into fixed values for the comparison.
CREATE UNIQUE INDEX IF NOT EXISTS audit_findings_unique
    ON audit_findings (finding_type, COALESCE(account_id, 0), COALESCE(employee_email, ''));

CREATE TABLE IF NOT EXISTS dead_letter (
    id          serial PRIMARY KEY,
    workflow    text NOT NULL,
    node        text,
    payload     jsonb,
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'replayed', 'discarded')),
    attempts    integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS renewal_alerts (
    contract_id     integer NOT NULL REFERENCES contracts (id),
    threshold_days  integer NOT NULL,
    sent_at         timestamptz NOT NULL DEFAULT now(),
    jira_key        text,
    PRIMARY KEY (contract_id, threshold_days)
);

CREATE TABLE IF NOT EXISTS monthly_reports (
    month       date PRIMARY KEY,                -- first day of the month
    totals      jsonb,
    summary     text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
