-- Question: does the excess readmission ratio differ by hospital ownership
-- type (all conditions together)?
--
-- Rows: hospitals with a ratio that match the General Information file (same
-- rows as v_hospital_condition).
--
-- Three averages:
--   avg_ratio           simple average over every result with a ratio
--   avg_ratio_counted   simple average over results whose discharges CMS
--                       published (volume_suppressed rows have NULL discharges)
--   weighted_avg_ratio  discharge-weighted average over those same results
-- Comparing avg_ratio with avg_ratio_counted shows the effect of dropping the
-- small, suppressed hospitals; comparing avg_ratio_counted with
-- weighted_avg_ratio shows the effect of weighting by volume.

SELECT
    h.hospital_ownership,
    COUNT(DISTINCT r.facility_id)                                   AS hospitals,
    COUNT(*)                                                        AS results,
    ROUND(100 * AVG(r.excess_readmission_ratio > 1.0), 1)           AS pct_above_1,
    ROUND(AVG(r.excess_readmission_ratio), 4)                       AS avg_ratio,
    COUNT(r.number_of_discharges)                                   AS results_counted,
    ROUND(AVG(CASE WHEN r.number_of_discharges IS NOT NULL
                   THEN r.excess_readmission_ratio END), 4)         AS avg_ratio_counted,
    ROUND(SUM(r.excess_readmission_ratio * r.number_of_discharges)
          / SUM(r.number_of_discharges), 4)                         AS weighted_avg_ratio,
    SUM(r.number_of_discharges)                                     AS discharges
FROM readmissions r
JOIN hospitals h ON h.facility_id = r.facility_id
WHERE r.has_ratio
GROUP BY h.hospital_ownership
ORDER BY avg_ratio DESC;
