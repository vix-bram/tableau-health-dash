#!/usr/bin/env python3
"""Clean the two raw CMS files into tidy CSVs ready for MySQL (Day 2).

Reads  data/raw/hrrp_readmissions.csv
       data/raw/hospital_general_information.csv
Writes data/clean/hospitals.csv      one row per hospital (5,4xx rows)
       data/clean/conditions.csv     the six HRRP conditions (lookup)
       data/clean/readmissions.csv   one row per hospital and condition

Nothing is deleted. Rows CMS suppressed are kept with flag columns, so each
view can decide what to include and the README can say exactly how many.
The script stops with an error if any check fails.

Usage:
    python scripts/clean_data.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"

# CMS writes these instead of a number when a value is missing or suppressed.
MISSING_TEXT = {"N/A", "Too Few to Report", "Not Available"}

# measure_name -> readable labels. Order sets condition_id.
CONDITIONS = [
    ("READM-30-AMI-HRRP", "AMI", "Heart attack"),
    ("READM-30-HF-HRRP", "HF", "Heart failure"),
    ("READM-30-PN-HRRP", "PN", "Pneumonia"),
    ("READM-30-COPD-HRRP", "COPD", "COPD"),
    ("READM-30-CABG-HRRP", "CABG", "Bypass surgery (CABG)"),
    ("READM-30-HIP-KNEE-HRRP", "HIP-KNEE", "Hip/knee replacement"),
]

# Footnote codes from CMS's Footnote Crosswalk (dataset y9us-9xdf).
FOOTNOTES = {
    1: "Too few cases to report",
    5: "Results not available for this period",
    7: "No cases met the criteria",
    29: "Partial-period data (CMS-approved exception)",
}

HOSPITAL_COLUMNS = [
    "facility_id", "facility_name", "city_town", "state", "hospital_type",
    "hospital_ownership", "emergency_services", "hospital_overall_rating",
]


class CheckFailed(Exception):
    pass


def check(condition, message):
    if not condition:
        raise CheckFailed(message)
    print(f"  ok  {message}")


def normalise(header):
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


def read_raw(filename):
    """Read every column as text so ids keep their leading zeros."""
    df = pd.read_csv(RAW / filename, dtype=str, keep_default_na=False)
    df.columns = [normalise(c) for c in df.columns]
    return df.apply(lambda col: col.str.strip()).replace("", pd.NA)


def to_number(series):
    """Known CMS placeholders become null; anything else non-numeric is an error."""
    text = series.where(~series.isin(MISSING_TEXT))
    numbers = pd.to_numeric(text, errors="coerce")
    unexpected = text[text.notna() & numbers.isna()].unique()
    if len(unexpected):
        raise CheckFailed(f"{series.name}: unexpected text values {list(unexpected)[:5]}")
    return numbers


def clean_hospitals(raw):
    df = raw[HOSPITAL_COLUMNS].copy()
    df["emergency_services"] = df["emergency_services"].map({"Yes": True, "No": False})
    df["hospital_overall_rating"] = to_number(df["hospital_overall_rating"]).astype("Int64")
    return df


def clean_conditions():
    return pd.DataFrame(
        [(i, measure, code, name) for i, (measure, code, name) in enumerate(CONDITIONS, start=1)],
        columns=["condition_id", "measure_name", "condition_code", "condition_name"],
    )


def clean_readmissions(raw, conditions):
    df = raw.copy()
    raw_readmissions = df["number_of_readmissions"]

    for column in ["number_of_discharges", "number_of_readmissions"]:
        df[column] = to_number(df[column]).astype("Int64")
    for column in ["excess_readmission_ratio", "predicted_readmission_rate",
                   "expected_readmission_rate"]:
        df[column] = to_number(df[column])
    for column in ["start_date", "end_date"]:
        df[column] = pd.to_datetime(df[column], format="%m/%d/%Y").dt.date

    df["footnote"] = pd.to_numeric(df["footnote"]).astype("Int64")
    df["footnote_text"] = df["footnote"].map(FOOTNOTES)

    # Flags: what each row can be used for.
    df["has_ratio"] = df["excess_readmission_ratio"].notna()
    df["volume_suppressed"] = df["has_ratio"] & (raw_readmissions == "Too Few to Report")
    df["partial_period"] = df["footnote"].eq(29).fillna(False).astype(bool)

    df = df.merge(conditions[["condition_id", "measure_name"]], on="measure_name", how="left")
    return df[[
        "facility_id", "condition_id", "number_of_discharges", "number_of_readmissions",
        "excess_readmission_ratio", "predicted_readmission_rate", "expected_readmission_rate",
        "footnote", "footnote_text", "has_ratio", "volume_suppressed", "partial_period",
        "start_date", "end_date",
    ]]


def run_checks(hospitals, conditions, readmissions):
    print("Checks:")
    check(hospitals["facility_id"].is_unique, f"hospitals: {len(hospitals):,} rows, facility_id unique")
    check(hospitals["facility_id"].str.len().eq(6).all(), "hospitals: every facility_id has 6 characters")
    ratings = hospitals["hospital_overall_rating"].dropna()
    check(ratings.between(1, 5).all(), "hospitals: star ratings are 1 to 5 or null")

    check(readmissions["condition_id"].notna().all(), "readmissions: every measure_name maps to a condition")
    duplicated = readmissions.duplicated(["facility_id", "condition_id"]).sum()
    check(duplicated == 0, f"readmissions: {len(readmissions):,} rows, no duplicate hospital+condition")
    check(readmissions["facility_id"].str.len().eq(6).all(), "readmissions: every facility_id has 6 characters")

    ratio = readmissions["excess_readmission_ratio"].dropna()
    check(ratio.between(0.2, 3).all(),
          f"readmissions: ratio between {ratio.min():.4f} and {ratio.max():.4f} (sanity range 0.2 to 3)")
    rebuilt = readmissions["predicted_readmission_rate"] / readmissions["expected_readmission_rate"]
    gap = (rebuilt - readmissions["excess_readmission_ratio"]).abs().max()
    check(gap < 0.001, f"readmissions: ratio = predicted / expected for every row (max gap {gap:.5f})")
    check(readmissions["has_ratio"].eq(readmissions["footnote"].isin([1, 5, 7]).eq(False)).all(),
          "readmissions: every missing ratio is explained by footnote 1, 5 or 7")

    # Outliers, printed for inspection rather than failing the build.
    print("\nMost extreme ratios (inspect these):")
    extremes = readmissions.dropna(subset=["excess_readmission_ratio"]).sort_values("excess_readmission_ratio")
    show = pd.concat([extremes.head(3), extremes.tail(3)])
    show = show.merge(hospitals[["facility_id", "facility_name"]], on="facility_id", how="left")
    show = show.merge(conditions[["condition_id", "condition_code"]], on="condition_id")
    print(show[["facility_id", "facility_name", "condition_code", "number_of_discharges",
                "excess_readmission_ratio"]].to_string(index=False))

    unmatched = ~readmissions["facility_id"].isin(hospitals["facility_id"])
    print("\nSummary:")
    print(f"  readmissions rows with no matching hospital: {unmatched.sum():,} "
          f"({readmissions.loc[unmatched, 'facility_id'].nunique()} hospitals)")
    print(f"  rows with a ratio:                {readmissions['has_ratio'].sum():,}")
    print(f"  rows with no ratio:               {(~readmissions['has_ratio']).sum():,}")
    print(f"  ratio but suppressed volumes:     {readmissions['volume_suppressed'].sum():,}")
    print(f"  partial-period ratios (fn 29):    {readmissions['partial_period'].sum():,}")
    print(f"  hospitals without a star rating:  {hospitals['hospital_overall_rating'].isna().sum():,}")


def main():
    hospitals = clean_hospitals(read_raw("hospital_general_information.csv"))
    conditions = clean_conditions()
    readmissions = clean_readmissions(read_raw("hrrp_readmissions.csv"), conditions)

    try:
        run_checks(hospitals, conditions, readmissions)
    except CheckFailed as error:
        print(f"  FAILED  {error}")
        return 1

    CLEAN.mkdir(parents=True, exist_ok=True)
    for name, df in [("hospitals", hospitals), ("conditions", conditions),
                     ("readmissions", readmissions)]:
        df.to_csv(CLEAN / f"{name}.csv", index=False)
    print(f"\nWrote clean CSVs to {CLEAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
