-- Query: All drone-related airport closures with details
SELECT 
    notam_id,
    airport_code,
    airport_name,
    issue_date,
    closure_start,
    closure_end,
    reason,
    weight,
    created_at
FROM airport_closures
WHERE is_drone_related = 1
ORDER BY closure_start DESC;