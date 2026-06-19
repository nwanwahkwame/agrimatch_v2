"""
Import chirps_daily_complete.csv into the chirps_daily table in Neon PostgreSQL.

Looks up district_id from ghana_districts by district_name (ignores the
district_id column in the CSV). Inserts in batches of 1000 rows using
psycopg2 execute_values with ON CONFLICT DO NOTHING, so re-running is safe.

Usage (from project root):
    python setup/import_chirps_csv.py --file "C:\\Users\\GOLDEN\\Downloads\\chirps_daily_complete.csv"
"""

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BATCH_SIZE     = 1000
PROGRESS_EVERY = 50_000

_SQL = """
    INSERT INTO chirps_daily (obs_date, district_id, mean_rainfall_mm, cell_count)
    VALUES %s
    ON CONFLICT (obs_date, district_id) DO NOTHING
"""


def main():
    parser = argparse.ArgumentParser(
        description="Import CHIRPS CSV into chirps_daily"
    )
    parser.add_argument("--file", required=True, help="Path to chirps_daily_complete.csv")
    args = parser.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}")
        sys.exit(1)

    t0 = time.time()

    # -- 1. Load CSV -------------------------------------------------------
    print()
    print(f"Loading {csv_path.name} ...")
    df = pd.read_csv(csv_path)
    total_csv = len(df)
    print(f"  {total_csv:,} rows loaded")

    # -- 2. Connect to Neon ------------------------------------------------
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    # psycopg2 requires postgresql://, not postgres://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print("Connecting to Neon PostgreSQL ...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    # -- 3. Load district name -> id mapping from ghana_districts ----------
    with conn.cursor() as cur:
        cur.execute("SELECT district_name, id FROM ghana_districts")
        district_map = {row[0]: row[1] for row in cur.fetchall()}
    print(f"  {len(district_map)} districts loaded from ghana_districts")

    # -- 4. Map CSV district_name -> db district_id ------------------------
    df["_db_id"] = df["district_name"].map(district_map)

    df_valid   = df[df["_db_id"].notna()].copy()
    df_invalid = df[df["_db_id"].isna()]

    unmatched_names = sorted(df_invalid["district_name"].unique())
    matched_district_count = df_valid["district_name"].nunique()

    print(f"  Districts matched   : {matched_district_count}")
    print(f"  Districts unmatched : {len(unmatched_names)}")

    if unmatched_names:
        print()
        print("  WARNING -- CSV district names with no match in ghana_districts:")
        for name in unmatched_names:
            print(f"    - {name}")

    # -- 5. Build insert tuples --------------------------------------------
    obs_dates    = pd.to_datetime(df_valid["obs_date"]).dt.date.tolist()
    district_ids = df_valid["_db_id"].astype(int).tolist()
    rainfalls    = df_valid["mean_rainfall_mm"].tolist()
    cell_counts  = [int(v) if pd.notna(v) else None for v in df_valid["cell_count"]]

    tuples = list(zip(obs_dates, district_ids, rainfalls, cell_counts))
    total  = len(tuples)

    print()
    print(f"Rows to insert : {total:,}")
    if total_csv - total > 0:
        print(f"Rows skipped (unmatched district) : {total_csv - total:,}")
    print()

    # -- 6. Batch insert ---------------------------------------------------
    rows_inserted  = 0
    rows_processed = 0
    last_logged    = 0

    for i in range(0, total, BATCH_SIZE):
        batch = tuples[i : i + BATCH_SIZE]

        with conn.cursor() as cur:
            execute_values(cur, _SQL, batch)
            rows_inserted += max(cur.rowcount, 0)
        conn.commit()

        rows_processed += len(batch)

        if rows_processed - last_logged >= PROGRESS_EVERY or rows_processed == total:
            print(f"  Inserted {rows_processed:,} / {total:,} rows ...")
            last_logged = rows_processed

    conn.close()

    # -- 7. Final summary --------------------------------------------------
    elapsed      = time.time() - t0
    rows_skipped = rows_processed - rows_inserted

    print()
    print("=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"  Total rows processed           : {rows_processed:,}")
    print(f"  Rows inserted (new)            : {rows_inserted:,}")
    print(f"  Rows skipped (already existed) : {rows_skipped:,}")
    print(f"  Districts matched successfully : {matched_district_count}")
    print(f"  Districts not matched          : {len(unmatched_names)}")
    if unmatched_names:
        for name in unmatched_names:
            print(f"    - {name}")
    print(f"  Time taken                     : {elapsed:.1f}s")
    print()


if __name__ == "__main__":
    main()
