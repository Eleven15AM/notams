-- Query: All drone-related NOTAMs with details
SELECT 
    notam_id,
    airport_code,
    airport_name,
    issue_date,
    valid_from,
    valid_to,
    body as reason,
    priority_score as score,
    created_at
FROM notams
WHERE is_drone_related = 1
  AND (notam_type != 'CANCEL' OR notam_type IS NULL)
ORDER BY valid_from DESC;