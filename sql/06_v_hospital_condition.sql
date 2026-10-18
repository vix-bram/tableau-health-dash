-- Flat view for Tableau: one row per hospital and condition, with the
-- hospital's attributes alongside its readmission results. Exported to
-- data/tableau/hospital_condition.csv by scripts/run_analysis.py, because
-- Tableau Public cannot connect to MySQL.
--
-- Rows: every HRRP hospital-condition row whose hospital matches the General
-- Information file (18,210 rows). The 20 unmatched hospitals (120 rows) are
-- left out because they have no name, state or ownership to show. Rows
-- without a ratio are kept so the "Find a hospital" page can say "not
-- available"; filter on has_ratio = 1 for every average or share.
--
-- Helper columns:
--   above_1   1 if the ratio is above 1.0, 0 if not, NULL if no ratio, so
--             AVG(above_1) in Tableau is the share of hospitals above 1.0
--   rankable  1 if the hospital had at least 100 discharges for the
--             condition (the cutoff used in 05_best_worst_hospitals.sql)

CREATE OR REPLACE VIEW v_hospital_condition AS
SELECT
    r.facility_id,
    h.facility_name,
    h.city_town,
    h.state,
    h.hospital_ownership,
    h.emergency_services,
    h.hospital_overall_rating,
    c.condition_code,
    c.condition_name,
    r.number_of_discharges,
    r.number_of_readmissions,
    r.excess_readmission_ratio,
    r.predicted_readmission_rate,
    r.expected_readmission_rate,
    CASE WHEN r.has_ratio THEN r.excess_readmission_ratio > 1.0 END  AS above_1,
    COALESCE(r.number_of_discharges >= 100, 0)                     AS rankable,
    r.has_ratio,
    r.volume_suppressed,
    r.partial_period,
    r.footnote,
    r.footnote_text,
    r.start_date,
    r.end_date
FROM readmissions r
JOIN hospitals  h ON h.facility_id = r.facility_id
JOIN conditions c ON c.condition_id = r.condition_id;
