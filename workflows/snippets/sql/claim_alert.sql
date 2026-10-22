-- "Claim alert" node of workflow D. Parameters in order: contract_id, threshold_days.
-- The alert is claimed BEFORE it is sent. The primary key (contract_id, threshold_days) lets only one run
-- insert the row; a second run (or an overlapping one) gets no row back and stops here, so a duplicate
-- alert is impossible. If sending fails the claim is released again (see release_claim.sql).
-- Returns the contract details used for the message and the Jira ticket.
WITH claimed AS (
    INSERT INTO renewal_alerts (contract_id, threshold_days)
    VALUES ($1::int, $2::int)
    ON CONFLICT (contract_id, threshold_days) DO NOTHING
    RETURNING contract_id, threshold_days
)
SELECT cl.contract_id, cl.threshold_days,
       c.contract_ref, t.name AS tool, t.vendor, c.seats, c.price_per_seat, c.billing_cycle,
       round(c.seats * c.price_per_seat * 12, 2) AS annual_value,
       c.start_date, c.end_date, c.notice_days, c.auto_renew, c.owner_email,
       (c.end_date - c.notice_days) AS notice_deadline,
       (c.end_date - c.notice_days) - (now() AT TIME ZONE 'Europe/Belgrade')::date AS days_left
FROM claimed cl
JOIN contracts c ON c.id = cl.contract_id
JOIN tools t ON t.id = c.tool_id;
