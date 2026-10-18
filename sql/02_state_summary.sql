-- Question: in which states do more hospitals readmit more patients than
-- expected (excess readmission ratio above 1.0), for each condition and for
-- all conditions together?
--
-- Rows: hospitals with a ratio that match the General Information file (same
-- rows as v_hospital_condition). "All conditions" pools every hospital and
-- condition result in the state, so pct_above_1 is the share of results above
-- 1.0, which is what Tableau shows when the condition filter is set to All.
--
-- Cutoff: a state is shown only if at least 10 hospitals have a ratio for that
-- condition (or overall). Chosen on Oct 18: it hides small samples, mostly
-- bypass surgery in small states, and keeps about 97% of rows.

WITH results AS (
    SELECT h.state, c.condition_name, r.facility_id, r.excess_readmission_ratio AS ratio
    FROM readmissions r
    JOIN hospitals  h ON h.facility_id = r.facility_id
    JOIN conditions c ON c.condition_id = r.condition_id
    WHERE r.has_ratio
),
by_condition AS (
    SELECT state, condition_name, facility_id, ratio FROM results
    UNION ALL
    SELECT state, 'All conditions', facility_id, ratio FROM results
)
SELECT
    condition_name,
    state,
    COUNT(DISTINCT facility_id)               AS hospitals,
    COUNT(*)                                  AS results,
    ROUND(100 * AVG(ratio > 1.0), 1)          AS pct_above_1,
    ROUND(AVG(ratio), 4)                      AS avg_ratio
FROM by_condition
GROUP BY condition_name, state
HAVING COUNT(DISTINCT facility_id) >= 10
ORDER BY condition_name, pct_above_1 DESC;
