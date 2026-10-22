-- "Mark replayed" and "Count attempt" nodes of the replay workflow. Parameters in order: dead_letter_id, replayed (true/false).
-- A successful replay closes the entry; a failed one stays open and only counts the attempt.
UPDATE dead_letter
SET status   = CASE WHEN $2::boolean THEN 'replayed' ELSE status END,
    attempts = attempts + 1
WHERE id = $1::int
RETURNING id, status, attempts;
