#!/usr/bin/env python3
"""First look at the two raw CMS files (Day 1).

Prints shape, dtypes, nulls, the text values hiding in number columns and the
distinct conditions, so we know what the Day 2 cleaning has to handle.

Usage (after scripts/download_data.py):
    python scripts/explore_data.py
"""

import re
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

# Columns that should hold numbers once cleaned (normalised names).
NUMBER_COLUMNS = {
    "hrrp_readmissions.csv": [
        "number_of_discharges",
        "excess_readmission_ratio",
        "predicted_readmission_rate",
        "expected_readmission_rate",
        "number_of_readmissions",
    ],
    "hospital_general_information.csv": ["hospital_overall_rating"],
}


def normalise(header):
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


def load(filename):
    # Everything as text: keeps facility_id's leading zeros and lets us see
    # the raw values before deciding how to convert them.
    df = pd.read_csv(RAW / filename, dtype=str, keep_default_na=False)
    df.columns = [normalise(c) for c in df.columns]
    return df.replace("", pd.NA)


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def describe(filename, df):
    section(filename)
    print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")

    print("\nColumns and dtypes (as loaded, all text on purpose):")
    print(df.dtypes.to_string())

    print("\nNulls (blank cells) per column, only columns that have any:")
    nulls = df.isna().sum()
    print(nulls[nulls > 0].to_string() if nulls.any() else "  none")

    print("\nText values in number columns:")
    for column in NUMBER_COLUMNS[filename]:
        values = df[column].dropna()
        text = values[pd.to_numeric(values, errors="coerce").isna()]
        if text.empty:
            print(f"  {column}: all numeric")
        else:
            counts = text.value_counts()
            detail = ", ".join(f'"{v}" x{n:,}' for v, n in counts.items())
            print(f"  {column}: {len(text):,} rows -> {detail}")

    ids = df["facility_id"].dropna().drop_duplicates()
    print(f"\nfacility_id: {ids.nunique():,} distinct, lengths {sorted(ids.str.len().unique())}, "
          f"{ids.str.startswith('0').sum():,} start with 0")


def main():
    hrrp = load("hrrp_readmissions.csv")
    info = load("hospital_general_information.csv")

    describe("hrrp_readmissions.csv", hrrp)

    print("\nDistinct measure_name values:")
    print(hrrp["measure_name"].value_counts().to_string())

    print("\nDate ranges (MM/DD/YYYY text):")
    for column in ["start_date", "end_date"]:
        print(f"  {column}: {hrrp[column].value_counts().to_dict()}")

    # A row is "suppressed" if any of its number columns holds text.
    numbers = hrrp[NUMBER_COLUMNS["hrrp_readmissions.csv"]]
    is_text = numbers.notna() & numbers.apply(pd.to_numeric, errors="coerce").isna()
    print(f"\nHRRP rows with text in at least one number column: {is_text.any(axis=1).sum():,}")
    print(f"HRRP rows with no usable excess_readmission_ratio: "
          f"{pd.to_numeric(hrrp['excess_readmission_ratio'], errors='coerce').isna().sum():,}")

    describe("hospital_general_information.csv", info)

    for column in ["hospital_type", "hospital_ownership", "emergency_services",
                   "hospital_overall_rating"]:
        print(f"\n{column}:")
        print(info[column].value_counts(dropna=False).to_string())

    section("Join check on facility_id")
    hrrp_ids = set(hrrp["facility_id"])
    info_ids = set(info["facility_id"])
    print(f"Hospitals in HRRP:                 {len(hrrp_ids):,}")
    print(f"Hospitals in General Information:  {len(info_ids):,}")
    print(f"In both:                           {len(hrrp_ids & info_ids):,}")
    print(f"General Info hospitals not in HRRP: {len(info_ids - hrrp_ids):,}")
    print(f"HRRP hospitals not in General Info: {len(hrrp_ids - info_ids):,}")


if __name__ == "__main__":
    main()
