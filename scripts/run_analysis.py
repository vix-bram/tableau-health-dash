#!/usr/bin/env python3
"""Run the Day 3 SQL analysis and export the Tableau file in one command.

Steps: create or replace the view in sql/06_v_hospital_condition.sql -> run
each analysis query (sql/01 to 05) and print its result -> export the view to
data/tableau/hospital_condition.csv -> check the exported file.

Run scripts/build_database.py first; this script reads the database it builds
and uses the same connection settings (.env in the project folder).

Usage:
    python scripts/run_analysis.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from build_database import connection_url

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "sql"
VIEW_FILE = SQL / "06_v_hospital_condition.sql"
EXPORT = ROOT / "data" / "tableau" / "hospital_condition.csv"

# Columns that can be NULL but are whole numbers; pandas would otherwise
# write them as floats (1.0) in the CSV.
NULLABLE_INTS = ["hospital_overall_rating", "number_of_discharges",
                 "number_of_readmissions", "above_1", "footnote"]


def statements(path):
    """Split a .sql file into statements, dropping -- comments."""
    lines = [line.split("--")[0] for line in path.read_text(encoding="utf-8").splitlines()]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def question(path):
    """The opening comment paragraph of a query file ("Question: ...")."""
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.lstrip("- ").strip()
        if not line:
            break
        words.append(line)
    return " ".join(words)


def main():
    load_dotenv(ROOT / ".env")
    engine = create_engine(connection_url(os.getenv("MYSQL_DATABASE", "hospital_readmissions")))
    pd.set_option("display.width", 250, "display.max_rows", 500, "display.max_columns", 30)

    print(f"Step 1: create the view ({VIEW_FILE.name})")
    try:
        with engine.begin() as conn:
            for statement in statements(VIEW_FILE):
                conn.execute(text(statement))
    except OperationalError as error:
        print(f"  FAILED  could not connect to MySQL: {error.orig.args[-1]}")
        print("  Check .env, that the MySQL80 service is running, and that build_database.py has run.")
        return 1
    print("  v_hospital_condition ready")

    print("\nStep 2: run the analysis queries")
    queries = sorted(p for p in SQL.glob("0*.sql") if p != VIEW_FILE)
    with engine.connect() as conn:
        for path in queries:
            (query,) = statements(path)  # one SELECT per file
            result = pd.read_sql(text(query), conn)
            print(f"\n=== {path.name}: {len(result):,} rows")
            print(f"    {question(path)}\n")
            print(result.to_string(index=False))

    print(f"\nStep 3: export the view to {EXPORT.relative_to(ROOT)}")
    with engine.connect() as conn:
        view = pd.read_sql(text("SELECT * FROM v_hospital_condition "
                                "ORDER BY facility_id, condition_code"), conn)
    view[NULLABLE_INTS] = view[NULLABLE_INTS].astype("Int64")
    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    view.to_csv(EXPORT, index=False)
    print(f"  {len(view):,} rows, {len(view.columns)} columns")

    print("\nStep 4: check the exported file")
    exported = pd.read_csv(EXPORT, dtype={"facility_id": str})
    checks = [
        (len(exported) == len(view), f"row count matches the view: {len(exported):,}"),
        (exported.facility_id.str.len().eq(6).all(), "every facility_id has 6 characters"),
        (exported.facility_id.str.startswith("0").any(), "leading zeros kept"),
        (not exported.duplicated(["facility_id", "condition_code"]).any(),
         "one row per hospital and condition"),
    ]
    failed = False
    for ok, message in checks:
        failed |= not ok
        print(f"  {'ok' if ok else 'FAILED'}  {message}")

    if failed:
        print("\nFinished with problems.")
        return 1
    print("\nAnalysis finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
