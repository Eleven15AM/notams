-- Query: Recent NOTAMs in the last 7 days
SELECT 
    notam_id,
    airport_code,
    airport_name,
    valid_from,
    valid_to,
    body as reason,
    CASE 
        WHEN is_drone_related = 1 THEN ' DRONE ACTIVITY'
        WHEN is_closure = 1 THEN 'CLOSURE'
        ELSE 'OTHER'
    END as notam_type,
    priority_score as score
FROM notams
WHERE valid_from >= datetime('now', '-7 days')
  AND (notam_type != 'CANCEL' OR notam_type IS NULL)
ORDER BY priority_score DESC, valid_from DESC;