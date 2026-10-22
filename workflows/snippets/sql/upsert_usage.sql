-- "Upsert usage" node. $1 = one batch (array) from "Normalise usage".
-- Rows whose account is not in the accounts table are counted in "unmatched", not silently lost.
WITH matched AS (
    SELECT a.id AS account_id, u.day, u.activity_count, u.spend_usd
    FROM jsonb_to_recordset($1::jsonb) AS u(
        tool text, external_id text, day date, activity_count int, spend_usd numeric)
    JOIN tools t    ON lower(split_part(t.name, ' ', 1)) = u.tool
    JOIN accounts a ON a.tool_id = t.id AND a.external_id = u.external_id
),
up AS (
    INSERT INTO usage_daily (account_id, day, activity_count, spend_usd)
    SELECT account_id, day, activity_count, spend_usd FROM matched
    ON CONFLICT (account_id, day) DO UPDATE SET
        activity_count = EXCLUDED.activity_count,
        spend_usd      = EXCLUDED.spend_usd
    RETURNING 1
)
SELECT (SELECT count(*) FROM up) AS upserted,
       jsonb_array_length($1::jsonb) - (SELECT count(*) FROM matched) AS unmatched;
