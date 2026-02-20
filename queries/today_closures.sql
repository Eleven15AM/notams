-- Query: NOTAMs active today
SELECT 
    notam_id,
    airport_code,
    airport_name,
    valid_from,
    valid_to,
    CASE 
        WHEN is_drone_related = 1 THEN ' DRONE'
        WHEN is_closure = 1 THEN 'CLOSURE'
        ELSE 'OTHER'
    END as type,
    body as reason
FROM notams
WHERE date(valid_from) = date('now')
   OR (
       valid_from <= datetime('now')
       AND (valid_to IS NULL OR valid_to >= datetime('now'))
   )
   AND (notam_type != 'CANCEL' OR notam_type IS NULL)
ORDER BY priority_score DESC, valid_from;