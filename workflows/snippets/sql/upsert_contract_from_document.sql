-- "Upsert contract" node of workflow C1. Parameters in order: valid (true/false), document_id, extracted data (JSON).
-- Runs for every document but only writes when valid is true. The contract_ref is the key, so a re-run updates
-- the same contract. (The validation has already refused data that conflicts with an existing contract.)
INSERT INTO contracts (tool_id, contract_ref, seats, price_per_seat, billing_cycle, start_date, end_date,
                       notice_days, auto_renew, owner_email, source_document_id)
SELECT t.id, d.contract_ref, d.seats, d.price_per_seat, d.billing_cycle, d.start_date, d.end_date,
       d.notice_days, d.auto_renew, d.owner, $2::int
FROM jsonb_to_record($3::jsonb) AS d(
         product text, contract_ref text, seats int, price_per_seat numeric, billing_cycle text,
         start_date date, end_date date, notice_days int, auto_renew boolean, owner text)
JOIN tools t ON lower(t.name) = lower(d.product)
WHERE $1::boolean
ON CONFLICT (contract_ref) DO UPDATE SET
    tool_id            = EXCLUDED.tool_id,
    seats              = EXCLUDED.seats,
    price_per_seat     = EXCLUDED.price_per_seat,
    billing_cycle      = EXCLUDED.billing_cycle,
    start_date         = EXCLUDED.start_date,
    end_date           = EXCLUDED.end_date,
    notice_days        = EXCLUDED.notice_days,
    auto_renew         = EXCLUDED.auto_renew,
    owner_email        = COALESCE(EXCLUDED.owner_email, contracts.owner_email),
    source_document_id = EXCLUDED.source_document_id
RETURNING id AS contract_id, contract_ref, (xmax = 0) AS inserted;
