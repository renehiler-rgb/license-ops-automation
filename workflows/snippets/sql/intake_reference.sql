-- "Load reference data" node of workflow C1. No parameters.
-- The tool names and the contracts already in the database. The validation uses them to
-- (1) accept only products we know and (2) refuse to overwrite an existing contract with different numbers.
SELECT
    (SELECT COALESCE(jsonb_agg(name), '[]'::jsonb) FROM tools) AS tools,
    (SELECT COALESCE(jsonb_agg(jsonb_build_object(
         'contract_ref', contract_ref, 'seats', seats, 'price_per_seat', price_per_seat,
         'start_date', to_char(start_date, 'YYYY-MM-DD'), 'end_date', to_char(end_date, 'YYYY-MM-DD'),
         'notice_days', notice_days, 'auto_renew', auto_renew)), '[]'::jsonb) FROM contracts) AS contracts;
