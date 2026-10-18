-- Question: for each condition, which hospitals have the lowest (best) and
-- highest (worst) excess readmission ratios, among hospitals with enough
-- patients for the ratio to be stable?
--
-- Cutoff: at least 100 discharges for that condition. Chosen on Oct 18: about
-- 4x CMS's own reporting floor of 25, and every condition still has 250 or
-- more eligible hospitals. Volume-suppressed rows (NULL discharges) are never
-- eligible. partial_period = 1 marks ratios CMS calculated from partial-period
-- data (footnote 29).
--
-- RANK() gives tied hospitals the same rank, so a condition can return more
-- than 10 rows on one side.

WITH eligible AS (
    SELECT
        c.condition_name,
        h.facility_name,
        h.city_town,
        h.state,
        h.hospital_ownership,
        r.number_of_discharges,
        r.excess_readmission_ratio,
        r.partial_period,
        RANK() OVER (PARTITION BY r.condition_id
                     ORDER BY r.excess_readmission_ratio ASC)  AS best_rank,
        RANK() OVER (PARTITION BY r.condition_id
                     ORDER BY r.excess_readmission_ratio DESC) AS worst_rank
    FROM readmissions r
    JOIN hospitals  h ON h.facility_id = r.facility_id
    JOIN conditions c ON c.condition_id = r.condition_id
    WHERE r.has_ratio
      AND r.number_of_discharges >= 100
)
SELECT
    condition_name,
    CASE WHEN best_rank <= 10 THEN 'Best' ELSE 'Worst' END     AS side,
    CASE WHEN best_rank <= 10 THEN best_rank ELSE worst_rank END AS `rank`,
    facility_name,
    city_town,
    state,
    hospital_ownership,
    number_of_discharges,
    excess_readmission_ratio,
    partial_period
FROM eligible
WHERE best_rank <= 10 OR worst_rank <= 10
ORDER BY condition_name, side, `rank`;
