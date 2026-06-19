"""
Import nasa_power_daily_complete.csv into the nasa_power_daily table
in Railway PostgreSQL.

Reads the CSV in chunks so it starts inserting immediately without
pre-loading all 1.66M rows into memory. ON CONFLICT DO NOTHING makes
re-runs safe -- already-inserted rows are skipped.

Usage (from project root):
    python setup/import_nasa_power_csv.py --file "C:\\Users\\GOLDEN\\Downloads\\nasa_power_daily_complete.csv"
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

CHUNK_SIZE     = 10_000
BATCH_SIZE     = 1000
PROGRESS_EVERY = 50_000

_SQL = """
    INSERT INTO nasa_power_daily
        (obs_date, district_id, temp_mean, temp_max, temp_min,
         solar_mj, humidity_pct, wind_ms, et0_mm)
    VALUES %s
    ON CONFLICT (obs_date, district_id) DO NOTHING
"""

_FLOAT_COLS = ["temp_mean", "temp_max", "temp_min", "solar_mj",
               "humidity_pct", "wind_ms", "et0_mm"]


def _connect(db_url):
    c = psycopg2.connect(
        db_url,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    c.autocommit = False
    return c


def _reconnect(db_url, attempt):
    time.sleep(5 * (attempt + 1))
    for _r in range(5):
        try:
            return _connect(db_url)
        except psycopg2.OperationalError:
            if _r == 4:
                raise
            time.sleep(10)


def _insert_batch(conn, db_url, batch):
    for attempt in range(6):
        try:
            with conn.cursor() as cur:
                execute_values(cur, _SQL, batch)
                inserted = max(cur.rowcount, 0)
            conn.commit()
            return conn, inserted
        except psycopg2.OperationalError as exc:
            if attempt == 5:
                raise
            print(f"  Connection dropped, reconnecting (attempt {attempt+1}) ...")
            try:
                conn.close()
            except Exception:
                pass
            conn = _reconnect(db_url, attempt)
    return conn, 0


def _chunk_to_tuples(chunk, district_map):
    chunk = chunk.copy()
    chunk["_db_id"] = chunk["district_name"].map(district_map)
    valid = chunk[chunk["_db_id"].notna()]
    if valid.empty:
        return [], valid["district_name"].nunique()

    obs_dates    = pd.to_datetime(valid["obs_date"]).dt.date.tolist()
    district_ids = valid["_db_id"].astype(int).tolist()

    # Replace NaN with None using object dtype per column
    float_data = {}
    for col in _FLOAT_COLS:
        arr = valid[col].to_numpy(dtype=object)
        # pandas NA / float nan -> None
        float_data[col] = [None if (v is None or v != v) else float(v) for v in arr]

    tuples = list(zip(
        obs_dates,
        district_ids,
        float_data["temp_mean"],
        float_data["temp_max"],
        float_data["temp_min"],
        float_data["solar_mj"],
        float_data["humidity_pct"],
        float_data["wind_ms"],
        float_data["et0_mm"],
    ))
    return tuples, valid["district_name"].nunique()


def main():
    parser = argparse.ArgumentParser(
        description="Import NASA POWER CSV into nasa_power_daily"
    )
    parser.add_argument("--file", required=True,
                        help="Path to nasa_power_daily_complete.csv")
    args = parser.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    t0 = time.time()

    # -- 1. Load district map ------------------------------------------------
    print()
    print("Connecting to Railway PostgreSQL ...", flush=True)
    _tmp = _connect(db_url)
    with _tmp.cursor() as cur:
        cur.execute("SELECT district_name, id FROM ghana_districts")
        district_map = {row[0]: row[1] for row in cur.fetchall()}
    _tmp.close()
    print(f"  {len(district_map)} districts loaded from ghana_districts", flush=True)

    # -- 2. Find how many rows already exist so we can skip them ------------
    print("Checking rows already in DB ...", flush=True)
    _tmp2 = _connect(db_url)
    with _tmp2.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nasa_power_daily")
        already_in_db = cur.fetchone()[0]
    _tmp2.close()
    chunks_to_skip = max(0, (already_in_db // CHUNK_SIZE) - 1)  # 1 chunk overlap for safety
    print(f"  {already_in_db:,} rows already in DB -- skipping first {chunks_to_skip} chunks", flush=True)
    print()

    # -- 3. Open insert connection and stream CSV in chunks ------------------
    conn = _connect(db_url)

    rows_processed = 0
    rows_inserted  = 0
    last_logged    = 0
    unmatched_names = set()

    import itertools
    reader = pd.read_csv(csv_path, chunksize=CHUNK_SIZE)

    # Fast-forward past already-inserted data
    if chunks_to_skip > 0:
        for _ in itertools.islice(reader, chunks_to_skip):
            pass
        rows_processed = chunks_to_skip * CHUNK_SIZE
        print(f"  Skipped to row {rows_processed:,}", flush=True)

    for chunk in reader:
        tuples, _ = _chunk_to_tuples(chunk, district_map)

        # track any unmatched districts
        chunk["_db_id"] = chunk["district_name"].map(district_map)
        unmatched_names.update(chunk[chunk["_db_id"].isna()]["district_name"].unique())

        for i in range(0, len(tuples), BATCH_SIZE):
            batch = tuples[i : i + BATCH_SIZE]
            conn, inserted = _insert_batch(conn, db_url, batch)
            rows_inserted  += inserted
            rows_processed += len(batch)

            if rows_processed - last_logged >= PROGRESS_EVERY:
                elapsed = time.time() - t0
                print(f"  Processed {rows_processed:,} rows  ({elapsed:.0f}s) ...", flush=True)
                last_logged = rows_processed

    conn.close()

    # -- 4. Summary ----------------------------------------------------------
    elapsed      = time.time() - t0
    rows_skipped = rows_processed - rows_inserted

    print()
    print("=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"  Total rows processed           : {rows_processed:,}")
    print(f"  Rows inserted (new)            : {rows_inserted:,}")
    print(f"  Rows skipped (already existed) : {rows_skipped:,}")
    print(f"  Districts not matched          : {len(unmatched_names)}")
    if unmatched_names:
        for name in sorted(unmatched_names):
            print(f"    - {name}")
    print(f"  Time taken                     : {elapsed:.1f}s")
    print()


if __name__ == "__main__":
    main()
