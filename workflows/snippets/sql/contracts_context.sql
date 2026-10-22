-- "Load contracts" node of workflow C2. No parameters.
-- The structured contract rows, for exact dates and numbers (the text chunks can be vague about them).
-- Returns ONE row with a JSON array. The annual value is seats x price x 12.
SELECT COALESCE(jsonb_agg(jsonb_build_object(
           'contract_ref', c.contract_ref,
           'tool', t.name,
           'vendor', t.vendor,
           'seats', c.seats,
           'price_per_seat_per_month_usd', c.price_per_seat,
           'annual_value_usd', round(c.seats * c.price_per_seat * 12, 2),
           'billing_cycle', c.billing_cycle,
           'start_date', to_char(c.start_date, 'YYYY-MM-DD'),
           'end_date', to_char(c.end_date, 'YYYY-MM-DD'),
           'notice_days', c.notice_days,
           'notice_deadline', to_char(c.end_date - c.notice_days, 'YYYY-MM-DD'),
           'auto_renew', c.auto_renew,
           'owner', c.owner_email) ORDER BY c.contract_ref), '[]'::jsonb) AS contracts
FROM contracts c
JOIN tools t ON t.id = c.tool_id;
