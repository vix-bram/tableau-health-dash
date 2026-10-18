#!/usr/bin/env python3
"""Rebuild the MySQL database from the raw CMS files in one command (Day 2).

Steps: run clean_data.py -> create the database if needed -> run sql/schema.sql
(drops and recreates the tables) -> load data/clean/*.csv -> check the
row counts inside MySQL match the CSVs.

Connection settings come from environment variables, or from a .env file in
the project folder (git-ignored, so the password never reaches GitHub):
    MYSQL_USER=root
    MYSQL_PASSWORD=...
    MYSQL_HOST=localhost       (optional, default localhost)
    MYSQL_PORT=3306            (optional, default 3306)
    MYSQL_DATABASE=...         (optional, default hospital_readmissions)

Usage:
    python scripts/build_database.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

import clean_data

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
SCHEMA = ROOT / "sql" / "schema.sql"

# Load order matters: readmissions references conditions.
TABLES = ["hospitals", "conditions", "readmissions"]


def connection_url(database=None):
    missing = [name for name in ("MYSQL_USER", "MYSQL_PASSWORD") if not os.getenv(name)]
    if missing:
        sys.exit(f"Missing {', '.join(missing)}. Add them to .env in the project folder.")
    return URL.create(
        "mysql+pymysql",
        username=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=database,
    )


def schema_statements():
    """Split schema.sql into statements, dropping -- comments."""
    lines = [line.split("--")[0] for line in SCHEMA.read_text(encoding="utf-8").splitlines()]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def read_clean(name):
    # facility_id stays text; everything else pandas can infer.
    return pd.read_csv(CLEAN / f"{name}.csv", dtype={"facility_id": str})


def main():
    load_dotenv(ROOT / ".env")
    database = os.getenv("MYSQL_DATABASE", "hospital_readmissions")

    print("Step 1: clean the raw files\n")
    if clean_data.main() != 0:
        return 1

    print(f"\nStep 2: create database `{database}` and tables")
    server = create_engine(connection_url())
    with server.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database}` "
                          "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
        version = conn.execute(text("SELECT VERSION()")).scalar()
    print(f"  MySQL {version}")
    if int(version.split(".")[0]) < 8:
        print("  FAILED  MySQL 8.0 or later is needed for CTEs and RANK()")
        return 1

    engine = create_engine(connection_url(database))
    with engine.begin() as conn:
        for statement in schema_statements():
            conn.execute(text(statement))
    print(f"  ran {SCHEMA.relative_to(ROOT)}")

    print("\nStep 3: load the clean CSVs")
    frames = {name: read_clean(name) for name in TABLES}
    with engine.begin() as conn:
        for name in TABLES:
            frames[name].to_sql(name, conn, if_exists="append", index=False, chunksize=2000)
            print(f"  {name}: {len(frames[name]):,} rows")

    print("\nStep 4: check the database")
    failed = False
    with engine.connect() as conn:
        for name in TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            ok = count == len(frames[name])
            failed |= not ok
            print(f"  {'ok' if ok else 'FAILED'}  {name}: {count:,} rows in MySQL")
        unmatched = conn.execute(text("""
            SELECT COUNT(*) AS readmission_rows, COUNT(DISTINCT r.facility_id) AS hospitals
            FROM readmissions r
            LEFT JOIN hospitals h ON h.facility_id = r.facility_id
            WHERE h.facility_id IS NULL
        """)).one()
        print(f"  readmissions rows with no matching hospital: {unmatched.readmission_rows:,} "
              f"({unmatched.hospitals} hospitals)")
        leading_zero = conn.execute(text(
            "SELECT COUNT(*) FROM hospitals WHERE facility_id LIKE '0%'")).scalar()
        ok = leading_zero > 0
        failed |= not ok
        print(f"  {'ok' if ok else 'FAILED'}  leading zeros kept: {leading_zero:,} facility_ids start with 0")

    if failed:
        print("\nFinished with problems.")
        return 1
    print(f"\nDatabase `{database}` rebuilt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
