-- Schema for the Hospital Readmissions Dashboard (MySQL 8.0+).
-- Run by scripts/build_database.py, which drops and rebuilds these tables
-- from data/clean/*.csv, so every statement must be safe to re-run.

DROP TABLE IF EXISTS readmissions;
DROP TABLE IF EXISTS conditions;
DROP TABLE IF EXISTS hospitals;

-- One row per hospital (CMS Hospital General Information).
CREATE TABLE hospitals (
    facility_id             VARCHAR(6)   NOT NULL,  -- text: keeps leading zeros
    facility_name           VARCHAR(255) NOT NULL,
    city_town               VARCHAR(100),
    state                   CHAR(2)      NOT NULL,
    hospital_type           VARCHAR(100),
    hospital_ownership      VARCHAR(100),
    emergency_services      BOOLEAN,
    hospital_overall_rating TINYINT,                -- 1 to 5; NULL = "Not Available"
    PRIMARY KEY (facility_id),
    KEY idx_hospitals_state (state),
    KEY idx_hospitals_ownership (hospital_ownership)
);

-- The six HRRP conditions (lookup).
CREATE TABLE conditions (
    condition_id   TINYINT      NOT NULL,
    measure_name   VARCHAR(40)  NOT NULL,           -- CMS code, e.g. READM-30-HF-HRRP
    condition_code VARCHAR(10)  NOT NULL,           -- short code, e.g. HF
    condition_name VARCHAR(60)  NOT NULL,           -- readable label, e.g. Heart failure
    PRIMARY KEY (condition_id),
    UNIQUE KEY uq_conditions_measure (measure_name)
);

-- One row per hospital and condition (CMS Hospital Readmissions Reduction Program).
-- No foreign key to hospitals: 20 HRRP hospitals are missing from the General
-- Information file, and their rows are kept and reported rather than dropped.
CREATE TABLE readmissions (
    facility_id                VARCHAR(6)    NOT NULL,
    condition_id               TINYINT       NOT NULL,
    number_of_discharges       INT,                 -- NULL when CMS suppressed it
    number_of_readmissions     INT,                 -- NULL when "N/A" or "Too Few to Report"
    excess_readmission_ratio   DECIMAL(6,4),        -- predicted / expected; > 1 = worse than expected
    predicted_readmission_rate DECIMAL(7,4),
    expected_readmission_rate  DECIMAL(7,4),
    footnote                   TINYINT,             -- CMS footnote code
    footnote_text              VARCHAR(100),
    has_ratio                  BOOLEAN       NOT NULL,  -- FALSE: no ratio (footnote 1, 5 or 7)
    volume_suppressed          BOOLEAN       NOT NULL,  -- ratio present, counts hidden (fewer than 11 readmissions)
    partial_period             BOOLEAN       NOT NULL,  -- footnote 29: partial-period data
    start_date                 DATE          NOT NULL,
    end_date                   DATE          NOT NULL,
    PRIMARY KEY (facility_id, condition_id),
    KEY idx_readmissions_condition (condition_id),
    CONSTRAINT fk_readmissions_condition
        FOREIGN KEY (condition_id) REFERENCES conditions (condition_id)
);
