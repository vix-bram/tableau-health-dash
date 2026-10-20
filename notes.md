# Notes

## Session 1: first look at the data

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
2. **"Minimum discharges" will silently drop rows.** 3,683 rows have a ratio but "N/A" discharges and "Too Few to Report" readmissions. These are small-volume hospitals. A minimum-discharges filter in Tableau will drop them all, not just the ones below the threshold. Decide in Session 2 how to treat them.
3. **The ratios sit very tightly around 1.0.** Mean 1.002, median 0.997, middle 50% between 0.958 and 1.042, range 0.47 to 1.63. About 48% of rows with a ratio are above 1.0. "Above 1.0" is close to a coin flip, so the dashboard should also show how far above.
4. **Star ratings:** 381 of the 3,035 matched hospitals have no star rating. That matters for View 4.

### Join on facility_id
- Always 6 characters; 559 HRRP hospitals start with 0. Reading as text works.
- 3,055 HRRP hospitals, of which **3,035 match** General Information. **20 HRRP hospitals have no match.** 2,384 General Information hospitals aren't in HRRP (expected: psychiatric, critical access, children's and others).

### Other
- `measure_name` values are codes, not names: READM-30-AMI / CABG / COPD / HF / HIP-KNEE / PN-HRRP. Map them to readable labels in Session 2.
- General Information has 38 columns. We only need about 7.

## Session 2: cleaning and MySQL (Oct 18)

- `scripts/build_database.py` rebuilds everything in one command and all checks pass. The ratio always equals predicted / expected (max gap 0.00006), and every missing ratio is explained by footnote 1, 5 or 7.
- **All six of the most extreme ratios are hip/knee replacement.** The lowest (0.47 to 0.56) are specialist orthopaedic and surgical hospitals, such as Kansas City Orthopaedic Institute and Salina Surgical Hospital. The highest (1.57 to 1.63) are general hospitals. That could be a finding about specialist hospitals. Check it in Session 3.
- **Nationally, every condition is about 50/50.** 47 to 50% of hospitals are above 1.0, and the average ratio is about 1.00 for all six conditions. That follows from how CMS calibrates "expected", which centres the national picture on 1.0. So View 2 will look flat, and saying "condition X is the problem" isn't supported. The real variation is between states, ownership types and individual hospitals. Consider reworking View 2 to show the *spread* per condition (how far the worst hospitals sit above 1.0) rather than the share above 1.0.
- MySQL: database `hospital_readmissions`, user `readmissions` (rights on this database only). Credentials are in `.env`, which is git-ignored.

## Session 3: SQL analysis and export (Oct 18)

Source: `python scripts/run_analysis.py` (after `build_database.py`). It creates the view, runs `sql/01` to `05` and exports `data/tableau/hospital_condition.csv`. These are observations, not findings yet. Check them against the Tableau views in Session 4.

### Decisions
- **Which rows count.** Every query uses hospitals that match General Information, the same rows as the Tableau view, so Session 4 can be reconciled exactly. The view has 18,210 rows from 3,035 hospitals. The 20 unmatched hospitals (120 rows) are left out because they have no name, state or ownership.
- **Numbers on matched rows** (use these in the README): **11,681** rows have a ratio (11,720 in the whole file), **3,668** are volume-suppressed (3,683 in the whole file), and all 377 partial-period rows are matched.
- **State cutoff: at least 10 hospitals with a ratio**, applied per condition. 238 of 306 state × condition cells are shown, covering about 97% of rows. Seven small states have fewer than 10 hospitals with a ratio even for all conditions together: DC, DE and VT (6 each), ND (7), AK and WY (8 each) and RI (9), so they will be blank on the map.
- **Ranking cutoff: at least 100 discharges.** That is about 4× CMS's floor of 25, and every condition still has 250 or more eligible hospitals. A cutoff of 200 would have left bypass surgery with only 110. Volume-suppressed rows have NULL discharges, so they can never be ranked.
- **Weighted averages** only use rows whose discharges are published. Query 03 therefore also shows a simple average over the same rows, which separates the effect of weighting from the effect of dropping small hospitals.
- **The view has helper columns:** `above_1` (1/0/NULL, so `AVG(above_1)` = share above 1.0) and `rankable` (100 or more discharges).

### What the numbers show
1. **Conditions differ in spread, not in share above 1.0.** Every condition has 47 to 50% of hospitals above 1.0 and an average of about 1.00. The spread varies widely, though. The standard deviation is 0.156 for hip/knee compared with 0.046 for COPD, and 23% of hip/knee hospitals are more than 10% above expected compared with 3% for COPD. **This answers the View 2 question: show the spread per condition**, not the share above 1.0.
2. **States vary much more than conditions.** The share of results above 1.0 runs from 65% (NJ) and 63% (MA) down to 19% (MT) and 20% (ID, UT). At first glance, high states cluster in the Northeast and South, and low ones in the Mountain West and Northwest. Check this on the map.
3. **Proprietary (for-profit) hospitals sit highest:** 55% above 1.0, a simple average of 1.017 and a weighted average of 1.022, compared with 46.5% and 0.998 for private non-profits. **Physician-owned hospitals are lowest** (simple 0.954, weighted 0.862). Federal (13 hospitals) and Tribal (5 hospitals, no published discharges) are too small to chart on their own.
4. **Star ratings line up step by step.** The share above 1.0 falls from 73% at 1 star to 31% at 5 stars, and the average falls from 1.048 to 0.966. But the overall star rating includes a readmission measure group, so part of this link is built in. Say so in the README. 197 hospitals with a ratio have no star rating. The other 184 unrated hospitals in the notes above have no ratio at all.
5. **The hip/knee specialist pattern holds at 100 or more discharges.** At least 6 of the best 10 are orthopaedic or surgical specialty hospitals, and 4 are physician-owned, which probably explains finding 3. They are high-volume (578 to 2,393 discharges). The worst 10 are all general hospitals with only 101 to 292 discharges. Specialty and volume are mixed together, so don't claim a cause.
6. **The suppressed small hospitals average below 1.0.** In most ownership groups the average over counted rows is higher than the simple average. Weighting then pulls it down again, so large hospitals look slightly better than mid-sized ones. The choice of average shifts the story a little.

### To handle in Session 4
- View 2: chart the spread (for example share above 1.10 and below 0.90, or a box plot) rather than the share above 1.0.
- View 1: footnote the seven blank states.
- View 3: combine Federal and Tribal into "Other" or footnote them.
- The best/worst lists include two partial-period ratios (Ascension St Vincent Evansville for hip/knee, Kootenai Health for pneumonia). Footnote them if they appear.
- Don't open and save the CSV in Excel, because it drops the leading zeros from `facility_id`.

## Session 4: Tableau views (Oct 19)

### Setup
- Connected to `data/tableau/hospital_condition.csv`. `facility_id` is a string (keeps leading zeros) and `state` has the State/Province role.
- Converted to dimensions: Hospital Overall Rating, Emergency Services, Footnote, Has Ratio, Volume Suppressed, Partial Period, Rankable. `Above 1` stays a measure, so `AVG([Above 1])` is the share above 1.0 (Tableau skips the blank rows with no ratio). Default number format: percentage, 1 decimal.
- Calculated field `Hospitals with ratio` = `COUNTD(IF NOT ISNULL([Excess Readmission Ratio]) THEN [Facility Id] END)`, the same count as `COUNT(DISTINCT facility_id)` in `sql/02`.

### Reconcile (Tableau vs SQL)
| Check | SQL / CSV | Tableau | Match |
|---|---|---|---|
| National share above 1.0 | 48.1% (11,681 rows) | 48.1% | Yes |
| NJ, all conditions | 65.4%, 61 hospitals | 65.4%, 61 hospitals | Yes |
| Proprietary share above 1.0 | 54.9% (2,093 rows, 544 hospitals) | 54.9% | Yes |
| Proprietary, minimum 25 discharges | 63.4% | 63.4% | Yes |

### View 1: State map
- Filled map of `AVG([Above 1])` with a Condition Name dropdown (single value, "(All)" = all conditions pooled).
- Filter `Hospitals with ratio` at least 10, matching the SQL cutoff. Under All conditions the seven small states (DC, DE, VT, ND, AK, WY, RI) are blank, as expected.
- Colors: Orange-Blue diverging, reversed, centered at 50%. Orange = more than half of results above 1.0. Range 18.9% (MT) to 65.4% (NJ).
- Caption explains the measure and the blank states.

### View 2: Spread by condition
- Changed from the plan (share above 1.0 by condition) because Session 3 showed every condition sits at 47 to 50% above 1.0. The chart shows the spread instead.
- Diverging bars per condition. Calculated fields (default aggregation Average, number format `0.0%;0.0%`):
  - `Much worse (>1.10)` = `IF NOT ISNULL([Excess Readmission Ratio]) THEN IIF([Excess Readmission Ratio] > 1.1, 1, 0) END`
  - `Much better (<0.90)` = `IF NOT ISNULL([Excess Readmission Ratio]) THEN IIF([Excess Readmission Ratio] < 0.9, -1, 0) END` (negative so the bar points left)
- Both on one axis via Measure Values, Measure Names on Color (blue = better, orange = worse), sorted by Much worse descending.
- Matches the CSV: hip/knee 25.0% better / 23.1% worse, CABG 14.4 / 13.2, pneumonia 4.8 / 7.5, heart failure 5.4 / 6.7, heart attack 5.5 / 6.5, COPD 0.9 / 2.9.
- Small bars (COPD, pneumonia "better") are too narrow for labels; the tooltip shows the value.

### View 3: Ownership
- Bars of `AVG([Above 1])` by `Ownership group`, sorted descending, same diverging colors as the map (center 50%), reference line at 50% (parameter `Reference line 50%`, control hidden).
- `Ownership group` = Hospital Ownership with Government - Federal and Tribal combined as "Other (Federal, Tribal)".
- Minimum-discharges slider: parameter `Minimum discharges` (0 to 500, step 25) and filter `Meets minimum discharges` = `[Minimum discharges] = 0 OR [Number Of Discharges] >= [Minimum discharges]`. At 0 every hospital counts. Any higher value also drops the 3,668 volume-suppressed rows (blank discharges; the smallest published value is 27), so the shares jump: Proprietary 54.9% at 0, 63.4% at 25, 59.0% at 100. The order barely changes (for-profit and local government highest, physician-owned lowest).
- Filter `Hospitals with ratio` at least 10, the same rule as the map. It only affects "Other": 18 hospitals at 0, but 7 at 25 (Tribal has no published discharges), where it otherwise jumped to the top at 73.7%.
- Caption explains the slider, the grouping and the 10-hospital rule.

### Left for Session 5 polish
- Axis and legend titles: replace "Avg. Above 1" with "Share of results above 1.0".
- Widen the ownership name column so "Voluntary non-profit - ..." isn't cut off.
- Delete the test worksheet "Sheet 1".
- Star rating: rotate the "1 star ... 5 stars" headers to horizontal and hide the "Hospital Overall Rating" field label.

## Session 5: finish and assemble (Oct 20)

### View 4: Star rating
- Charted the **share above 1.0** rather than the average ratio (the plan's wording), so it matches Views 1 and 3. Averages of 0.97 to 1.05 look almost the same as bars; the shares show the step pattern clearly. The average ratio is in the tooltip.
- Bars of `AVG([Above 1])` by Hospital Overall Rating (discrete dimension), Null excluded, aliases "1 star" to "5 stars". Labels show the share and `n = <Hospitals with ratio>`. Same diverging colors (center 50%) and 50% reference line as View 3.
- Default number format for Excess Readmission Ratio set to 3 decimals.
- Matches the CSV: 1 star 72.5% (n = 169, avg 1.048), 2 stars 61.1% (567, 1.025), 3 stars 49.9% (840, 1.006), 4 stars 38.8% (758, 0.986), 5 stars 30.7% (287, 0.966). 197 hospitals with a ratio have no rating and are left out (caption says so).
- Caption notes that the star rating includes a readmission measure, so part of the link is built in.

### View 5: Hospital lookup
- 97 hospital names appear more than once, so the dropdown uses `Hospital` = `[Facility Name] + " (" + [City Town] + ", " + [State] + ")"`, which is unique for all 3,035 hospitals. Filter on Hospital, single value dropdown.
- Shows each ratio as "% more or fewer readmissions than expected" instead of the raw ratio (easier to read; the 1.0 line becomes the zero line):
  - `Readmissions vs expected` = `AVG([Excess Readmission Ratio]) - 1`
  - `State vs expected` = `AVG({FIXED [State], [Condition Name]: AVG([Excess Readmission Ratio])}) - 1`. FIXED computes before the hospital filter, so it is the state average across hospitals (each hospital counts equally). No 10-hospital cutoff here, so small states average only a few hospitals.
  - `Worse than expected` = `[Readmissions vs expected] > 0` on Color (orange True, blue False). Number format `+0.0%;-0.0%;0.0%`.
- State average drawn as a black reference line per cell (no label); value in the tooltip.
- Checked against the CSV: Southeast Health Medical Center (Dothan, AL) and Mount Sinai Hospital (New York, NY) match on all six conditions.

### Correction: what "volume suppressed" means
- Mount Sinai (a very large hospital) has suppressed discharges for hip/knee (ratio 0.577) and CABG. CMS hides the counts when a hospital has **fewer than 11 readmissions** for a condition, not only when the hospital is small. So suppression is partly triggered by having few readmissions, which goes with a low ratio. This is a selection effect and helps explain why suppressed rows average below 1.0 and why shares jump when View 3's minimum-discharges slider moves off 0.
- Fix the wording "small hospitals" in the View 3 caption and in the README (Session 6): say "results where CMS hid the counts (fewer than 11 readmissions)".
- Hospital lookup tooltip: show "Not published (fewer than 11 readmissions)" instead of a blank discharges value.
