# Notes

## Day 1: first look at the data (Oct 2026)

Source: `scripts/download_data.py`, then `scripts/explore_data.py`. Exact file versions are in `data/raw/download_log.json`.

### Row counts
- **HRRP:** 18,330 rows = 3,055 hospitals x 6 conditions. Matches the plan.
- **Hospital General Information:** 5,419 rows, one per hospital. The plan expected 5,432; the current CMS file has 13 fewer hospitals.
- All HRRP rows cover the same period: 07/01/2021 to 06/30/2024.

### Text in number columns
| Column | "N/A" | "Too Few to Report" |
|---|---|---|
| excess_readmission_ratio | 6,610 | 0 |
| predicted / expected_readmission_rate | 6,610 each | 0 |
| number_of_discharges | 10,088 | 0 |
| number_of_readmissions | 6,610 | 3,683 |
| hospital_overall_rating (General Info) | 2,245 "Not Available" | n/a |

- 10,293 HRRP rows have text in at least one number column. 6,610 rows have no usable ratio, leaving 11,720 rows with a ratio.
- The `footnote` column explains every missing ratio. The meanings come from CMS's Footnote Crosswalk dataset (y9us-9xdf, data.cms.gov/provider-data):
  - **1** (3,150 rows): "The number of cases/patients is too few to report."
  - **5** (3,255 rows): "Results are not available for this reporting period."
  - **7** (205 rows): "No cases met the criteria for this measure."
- **29** (377 rows) appears on rows that *do* have a ratio: "This measure was calculated using partial performance period data due to a CMS-approved exception." Keep these rows, but flag them and mention them as a limitation.

### Surprises
1. **Every hospital that matches is an Acute Care Hospital.** All 3,035 hospitals found in both files have `hospital_type = "Acute Care Hospitals"`. HRRP only covers acute care hospitals, so a hospital-type comparison (View 3) has nothing to compare. **Ownership (12 categories) still works.** View 3 should probably become ownership only, perhaps with emergency services as a second split.
2. **"Minimum discharges" will silently drop rows.** 3,683 rows have a ratio but "N/A" discharges and "Too Few to Report" readmissions. These are small-volume hospitals. A minimum-discharges filter in Tableau will drop them all, not just the ones below the threshold. Decide on Day 2 how to treat them.
3. **The ratios sit very tightly around 1.0.** Mean 1.002, median 0.997, middle 50% between 0.958 and 1.042, range 0.47 to 1.63. About 48% of rows with a ratio are above 1.0. "Above 1.0" is close to a coin flip, so the dashboard should also show how far above.
4. **Star ratings:** 381 of the 3,035 matched hospitals have no star rating. That matters for View 4.

### Join on facility_id
- Always 6 characters; 559 HRRP hospitals start with 0. Reading as text works.
- 3,055 HRRP hospitals, of which **3,035 match** General Information. **20 HRRP hospitals have no match.** 2,384 General Information hospitals aren't in HRRP (expected: psychiatric, critical access, children's and others).

### Other
- `measure_name` values are codes, not names: READM-30-AMI / CABG / COPD / HF / HIP-KNEE / PN-HRRP. Map them to readable labels on Day 2.
- General Information has 38 columns. We only need about 7.
