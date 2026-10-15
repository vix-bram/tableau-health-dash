#!/usr/bin/env python3
"""Download the two CMS datasets used by the Hospital Readmissions Dashboard.

Datasets (CMS Provider Data Catalog, data.cms.gov/provider-data):
  * Hospital Readmissions Reduction Program        (dataset id 9n3s-kdb3)
  * Hospital General Information                   (dataset id xubh-q36u)

Rather than hard-coding a file URL (CMS changes the file name every time it
refreshes a dataset), the script asks CMS's metadata endpoint for the current
download link, saves each CSV into data/raw/, checks that the key columns are
there, and writes data/raw/download_log.json so you can say exactly which
version of the data the analysis used.

Usage (from the project folder or from scripts/):
    python scripts/download_data.py

Standard library only: nothing to pip install.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://data.cms.gov/provider-data"
METADATA_PATH = "/api/1/metastore/schemas/dataset/items/{dataset_id}"
USER_AGENT = "hospital-readmissions-dashboard/1.0 (portfolio project)"
TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 3

# Column names are compared after normalising (lower case, punctuation -> "_"),
# because the CSV headers are title case ("Facility ID") while CMS's data
# dictionary uses snake_case ("facility_id").
DATASETS = {
    "hrrp": {
        "dataset_id": "9n3s-kdb3",
        "filename": "hrrp_readmissions.csv",
        "required_columns": [
            "facility_id",
            "state",
            "measure_name",
            "number_of_discharges",
            "excess_readmission_ratio",
            "predicted_readmission_rate",
            "expected_readmission_rate",
            "number_of_readmissions",
            "start_date",
            "end_date",
        ],
    },
    "hospital_info": {
        "dataset_id": "xubh-q36u",
        "filename": "hospital_general_information.csv",
        "required_columns": [
            "facility_id",
            "facility_name",
            "state",
            "hospital_type",
            "hospital_ownership",
            "emergency_services",
            "hospital_overall_rating",
        ],
    },
}


def project_root():
    """The folder that holds data/, sql/ and scripts/ (works from either place)."""
    here = Path(__file__).resolve().parent
    return here.parent if here.name == "scripts" else here


def normalise(header):
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


def open_url(url):
    """GET a URL with a few retries; returns an open response."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
            if attempt < MAX_ATTEMPTS:
                wait = 2 ** attempt
                print(f"  attempt {attempt} failed ({error}); retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"could not reach {url}: {last_error}")


def fetch_metadata(base_url, dataset_id):
    url = base_url.rstrip("/") + METADATA_PATH.format(dataset_id=dataset_id)
    with open_url(url) as response:
        return json.load(response)


def find_csv_url(metadata):
    """Pull the current CSV download link out of the dataset's metadata."""
    candidates = []
    for distribution in metadata.get("distribution", []):
        link = distribution.get("downloadURL") or distribution.get("data", {}).get("downloadURL")
        if link:
            candidates.append(link)
    for link in candidates:
        if link.lower().split("?")[0].endswith(".csv"):
            return link
    if candidates:
        return candidates[0]
    raise RuntimeError("the dataset metadata does not contain a download link")


def download_file(url, destination):
    """Stream to a temporary file, then move it into place, so a failed
    download never leaves a half-written CSV behind."""
    temporary = destination.with_name(destination.name + ".part")
    with open_url(url) as response, open(temporary, "wb") as out:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    temporary.replace(destination)
    return destination.stat().st_size


def inspect_csv(path, required_columns):
    """Count data rows and report any required columns that are missing."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            raise RuntimeError(f"{path.name} is empty")
        rows = sum(1 for row in reader if any(cell.strip() for cell in row))
    present = {normalise(name) for name in header}
    missing = [name for name in required_columns if name not in present]
    return header, rows, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--outdir", type=Path, default=None,
                        help="where to save the CSVs (default: <project>/data/raw)")
    parser.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)
    args = parser.parse_args()

    outdir = args.outdir or project_root() / "data" / "raw"
    outdir.mkdir(parents=True, exist_ok=True)

    log = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "datasets": {}}
    problems = []

    for key, spec in DATASETS.items():
        print(f"[{key}] dataset {spec['dataset_id']}")
        try:
            metadata = fetch_metadata(args.base_url, spec["dataset_id"])
            url = find_csv_url(metadata)
            destination = outdir / spec["filename"]
            print(f"  downloading {url}")
            size = download_file(url, destination)
            header, rows, missing = inspect_csv(destination, spec["required_columns"])
        except (RuntimeError, OSError, json.JSONDecodeError) as error:
            print(f"  FAILED: {error}")
            problems.append(f"{key}: {error}")
            continue

        print(f"  saved {destination}")
        print(f"  {rows:,} rows, {len(header)} columns, {size / 1024:,.0f} KB")
        if missing:
            print(f"  WARNING: missing expected columns: {', '.join(missing)}")
            problems.append(f"{key}: missing columns {', '.join(missing)}")

        log["datasets"][key] = {
            "dataset_id": spec["dataset_id"],
            "title": metadata.get("title"),
            "modified": metadata.get("modified"),
            "released": metadata.get("released") or metadata.get("issued"),
            "download_url": url,
            "file": str(destination.relative_to(outdir.parent.parent))
            if outdir.parent.parent in destination.parents else str(destination),
            "rows": rows,
            "columns": header,
            "bytes": size,
        }

    log_path = outdir / "download_log.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"\nWrote {log_path}")

    if problems:
        print("\nFinished with problems:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("All datasets downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
