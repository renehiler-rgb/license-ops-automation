-- "Upsert accounts" node. $1 = JSON array from "Normalise accounts".
-- The vendor key ('chatterly', ...) is matched to tools.name by its first word.
WITH up AS (
    INSERT INTO accounts (tool_id, external_id, email, seat_type, status, created_at, last_active_at)
    SELECT t.id, a.external_id, a.email, a.seat_type, a.status, a.created_at, a.last_active_at
    FROM jsonb_to_recordset($1::jsonb) AS a(
        tool text, external_id text, email text, seat_type text, status text,
        created_at timestamptz, last_active_at timestamptz)
    JOIN tools t ON lower(split_part(t.name, ' ', 1)) = a.tool
    ON CONFLICT (tool_id, external_id) DO UPDATE SET
        email          = EXCLUDED.email,
        seat_type      = EXCLUDED.seat_type,
        status         = EXCLUDED.status,
        created_at     = EXCLUDED.created_at,
        last_active_at = EXCLUDED.last_active_at
    RETURNING (xmax = 0) AS inserted
)
SELECT count(*) FILTER (WHERE inserted)     AS inserted,
       count(*) FILTER (WHERE NOT inserted) AS updated
FROM up;
