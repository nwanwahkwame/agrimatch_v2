"""
Migrate M1 price pipeline data from Neon to Railway PostgreSQL.

Copies: crop_reference, ingestion_log, raw_prices, clean_prices,
        price_quarantine  (in FK-safe order)

ghana_markets is NOT migrated here -- run populate_markets.py after
this script to rebuild it from clean_prices on Railway.

Before running, add the old Neon URL to .env as a second key:
    NEON_DATABASE_URL=postgresql://...neon.tech/agrimatch?sslmode=require...

Current DATABASE_URL must point to Railway (the destination).

Usage (from project root):
    python setup/migrate_neon_to_railway.py
"""

import os
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── Helpers ───────────────────────────────────────────────────────────────────

def connect(url: str, label: str):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url)
    conn.autocommit = False
    print(f"  Connected to {label}")
    return conn


def jsonify(val):
    """Wrap dicts/lists in Json() so psycopg2 writes them as JSONB."""
    if isinstance(val, (dict, list)):
        return pgx.Json(val)
    return val


def migrate_table(src_url, dst, table, select_sql, insert_sql,
                  jsonb_cols=(), batch_size=500):
    """Read all rows from src table, insert into dst, reset sequence.
    Opens a fresh Neon connection per table to avoid SSL idle-timeout drops."""
    src = connect(src_url, f"Neon/{table}")
    with src.cursor(cursor_factory=pgx.DictCursor) as cur:
        cur.execute(select_sql)
        raw_rows = cur.fetchall()
    src.close()

    if not raw_rows:
        print(f"  {table:<22} 0 rows -- skipping")
        return

    col_names = list(raw_rows[0].keys())
    tuples = []
    for row in raw_rows:
        t = tuple(
            jsonify(row[col]) if col in jsonb_cols else row[col]
            for col in col_names
        )
        tuples.append(t)

    inserted = 0
    for i in range(0, len(tuples), batch_size):
        chunk = tuples[i : i + batch_size]
        with dst.cursor() as cur:
            pgx.execute_values(cur, insert_sql, chunk)
            inserted += max(cur.rowcount, 0)
        dst.commit()

    # Reset the sequence so future autoincrement picks up after max(id)
    with dst.cursor() as cur:
        cur.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1)
            )
        """)
    dst.commit()

    print(f"  {table:<22} {len(raw_rows):>6} rows read  |  {inserted:>6} inserted")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    neon_url = os.environ.get("NEON_DATABASE_URL", "")
    rail_url = os.environ.get("DATABASE_URL", "")

    if not neon_url:
        print()
        print("ERROR: NEON_DATABASE_URL not set in .env")
        print("  Copy the old Neon connection string and add it as:")
        print("  NEON_DATABASE_URL=postgresql://...neon.tech/agrimatch?sslmode=require...")
        sys.exit(1)
    if not rail_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    print()
    print("Connecting to Railway (destination) ...")
    dst = connect(rail_url, "Railway (destination)")

    t0 = time.time()
    print()
    print(f"  {'Table':<22} {'Read':>6}         {'Inserted':>8}")
    print("  " + "-" * 50)

    # crop_reference (JSONB: unit_conversions, ARRAY: hdx_names, mofa_names)
    migrate_table(
        neon_url, dst, "crop_reference",
        select_sql="""
            SELECT id, internal_name, hdx_names, mofa_names,
                   default_unit, unit_conversions, is_byproduct_source
            FROM crop_reference ORDER BY id
        """,
        insert_sql="""
            INSERT INTO crop_reference
                (id, internal_name, hdx_names, mofa_names,
                 default_unit, unit_conversions, is_byproduct_source)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """,
        jsonb_cols=("unit_conversions",),
    )

    # ingestion_log (no JSONB or ARRAY)
    migrate_table(
        neon_url, dst, "ingestion_log",
        select_sql="""
            SELECT id, source, run_at, rows_fetched, rows_clean,
                   rows_quarantined, status, error_detail, file_ref
            FROM ingestion_log ORDER BY id
        """,
        insert_sql="""
            INSERT INTO ingestion_log
                (id, source, run_at, rows_fetched, rows_clean,
                 rows_quarantined, status, error_detail, file_ref)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """,
    )

    # raw_prices (JSONB: raw_payload) -- must come before clean_prices
    migrate_table(
        neon_url, dst, "raw_prices",
        select_sql="""
            SELECT id, source, ingested_at, raw_payload, file_ref
            FROM raw_prices ORDER BY id
        """,
        insert_sql="""
            INSERT INTO raw_prices (id, source, ingested_at, raw_payload, file_ref)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """,
        jsonb_cols=("raw_payload",),
    )

    # clean_prices (FK to raw_prices)
    migrate_table(
        neon_url, dst, "clean_prices",
        select_sql="""
            SELECT id, raw_id, market, region, district_id, crop,
                   unit, price_ghs, price_date, source, created_at
            FROM clean_prices ORDER BY id
        """,
        insert_sql="""
            INSERT INTO clean_prices
                (id, raw_id, market, region, district_id, crop,
                 unit, price_ghs, price_date, source, created_at)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """,
    )

    # price_quarantine (JSONB: raw_payload, FK to raw_prices)
    migrate_table(
        neon_url, dst, "price_quarantine",
        select_sql="""
            SELECT id, raw_id, rejection_reason, raw_payload, quarantined_at
            FROM price_quarantine ORDER BY id
        """,
        insert_sql="""
            INSERT INTO price_quarantine
                (id, raw_id, rejection_reason, raw_payload, quarantined_at)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
        """,
        jsonb_cols=("raw_payload",),
    )

    elapsed = time.time() - t0
    dst.close()

    print()
    print(f"Migration complete in {elapsed:.1f}s")
    print()
    print("Next steps:")
    print("  python setup/populate_markets.py   -- rebuilds ghana_markets from clean_prices")
    print("  python setup/import_chirps_csv.py  --file ...")
    print("  python setup/import_nasa_power_csv.py --file ...")


if __name__ == "__main__":
    main()
