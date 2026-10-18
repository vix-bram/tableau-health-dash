-- Question: for each condition, what share of hospitals readmit more patients
-- than expected (excess readmission ratio above 1.0), and how widely do the
-- ratios spread around 1.0?
--
-- Rows: hospitals with a ratio (has_ratio) that match the General Information
-- file, the same rows as v_hospital_condition, so Tableau can be reconciled
-- against this output. CMS calibrates "expected" so the national picture
-- centres on 1.0, so the spread columns (SD, share beyond 1.10 / 0.90, min,
-- max) are reported next to the share above 1.0.

SELECT
    c.condition_name,
    COUNT(*)                                                    AS hospitals,
    ROUND(100 * AVG(r.excess_readmission_ratio > 1.0), 1)       AS pct_above_1,
    ROUND(AVG(r.excess_readmission_ratio), 4)                   AS avg_ratio,
    ROUND(STDDEV_SAMP(r.excess_readmission_ratio), 4)           AS sd_ratio,
    ROUND(100 * AVG(r.excess_readmission_ratio > 1.10), 1)      AS pct_above_1_10,
    ROUND(100 * AVG(r.excess_readmission_ratio < 0.90), 1)      AS pct_below_0_90,
    MIN(r.excess_readmission_ratio)                             AS min_ratio,
    MAX(r.excess_readmission_ratio)                             AS max_ratio
FROM readmissions r
JOIN hospitals  h ON h.facility_id = r.facility_id
JOIN conditions c ON c.condition_id = r.condition_id
WHERE r.has_ratio
GROUP BY c.condition_id, c.condition_name
ORDER BY sd_ratio DESC;
