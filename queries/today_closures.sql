-- Query: Airport closures for today
SELECT 
    notam_id,
    airport_code,
    airport_name,
    closure_start,
    closure_end,
    CASE 
        WHEN is_drone_related = 1 THEN ' DRONE'
        ELSE 'Normal'
    END as type,
    reason
FROM airport_closures
WHERE date(closure_start) = date('now')
   OR (
       closure_start <= datetime('now')
       AND (closure_end IS NULL OR closure_end >= datetime('now'))
   )
ORDER BY weight DESC, closure_start;