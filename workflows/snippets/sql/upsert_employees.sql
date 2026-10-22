-- "Upsert employees" node. $1 = JSON array from "Normalise employees" ({{ [JSON.stringify($json.employees)] }}).
WITH up AS (
    INSERT INTO employees (email, name, team, cost_center, status, start_date, end_date)
    SELECT e.email, e.name, e.team, e.cost_center, e.status, e.start_date, e.end_date
    FROM jsonb_to_recordset($1::jsonb) AS e(
        email text, name text, team text, cost_center text,
        status text, start_date date, end_date date)
    ON CONFLICT (email) DO UPDATE SET
        name        = EXCLUDED.name,
        team        = EXCLUDED.team,
        cost_center = EXCLUDED.cost_center,
        status      = EXCLUDED.status,
        start_date  = EXCLUDED.start_date,
        end_date    = EXCLUDED.end_date
    RETURNING (xmax = 0) AS inserted        -- xmax = 0 means the row was newly inserted
)
SELECT count(*) FILTER (WHERE inserted)     AS inserted,
       count(*) FILTER (WHERE NOT inserted) AS updated
FROM up;
