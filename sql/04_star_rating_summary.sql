-- Question: do hospitals with a higher CMS overall star rating (1 to 5) have
-- lower excess readmission ratios?
--
-- Rows: hospitals with a ratio that match the General Information file (same
-- rows as v_hospital_condition). Hospitals whose rating is "Not Available"
-- are listed as "Not rated" at the bottom so the number left out of View 4 is
-- visible; they are not part of the 1-to-5 comparison.
--
-- Caution: the star rating itself includes a readmission measure group, so
-- some link between the two is built in. Treat this as an association.

SELECT
    COALESCE(CAST(h.hospital_overall_rating AS CHAR), 'Not rated')  AS star_rating,
    COUNT(DISTINCT r.facility_id)                                   AS hospitals,
    COUNT(*)                                                        AS results,
    ROUND(100 * AVG(r.excess_readmission_ratio > 1.0), 1)           AS pct_above_1,
    ROUND(AVG(r.excess_readmission_ratio), 4)                       AS avg_ratio,
    ROUND(SUM(r.excess_readmission_ratio * r.number_of_discharges)
          / SUM(r.number_of_discharges), 4)                         AS weighted_avg_ratio
FROM readmissions r
JOIN hospitals h ON h.facility_id = r.facility_id
WHERE r.has_ratio
GROUP BY h.hospital_overall_rating
ORDER BY h.hospital_overall_rating IS NULL, h.hospital_overall_rating;
