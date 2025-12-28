-- Query: Recent airport closures in the last 7 days
SELECT 
    notam_id,
    airport_code,
    airport_name,
    closure_start,
    closure_end,
    reason,
    CASE 
        WHEN is_drone_related = 1 THEN ' DRONE ACTIVITY'
        ELSE 'OTHER'
    END as closure_type,
    weight
FROM airport_closures
WHERE closure_start >= datetime('now', '-7 days')
ORDER BY weight DESC, closure_start DESC;