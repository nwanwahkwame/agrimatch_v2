"""
Export feature_store to CSV for Colab training.

Uses psycopg2 COPY TO STDOUT — PostgreSQL streams directly to file,
no per-row Python processing. Fastest method for cloud databases.

Usage (from project root):
    python setup/export_training_data.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

OUT_PATH = Path(__file__).parent.parent / "data" / "feature_store_training.csv"

# Numeric columns to check for null rates
_NUMERIC_COLS = [
    "price_ghs", "lag_7d", "lag_14d", "lag_30d", "lag_90d",
    "rolling_mean_30d", "rolling_std_30d", "rolling_mean_90d",
    "rolling_min_30d", "rolling_max_30d",
    "price_momentum_7d", "price_momentum_30d",
    "sin_week", "cos_week", "sin_month", "cos_month",
    "spi_30day", "et0_mm", "csi_value", "fuel_price_diesel",
    "district_id",
]


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # ── Step 1: summary stats (single query) ──────────────────────────────
    print("\nFetching summary stats...", flush=True)

    null_exprs = ",\n    ".join(
        f"COUNT(*) - COUNT({c}) AS null_{c}" for c in _NUMERIC_COLS
    )
    cur.execute(f"""
        SELECT
            COUNT(*)                        AS total_rows,
            MIN(feature_date)               AS date_min,
            MAX(feature_date)               AS date_max,
            COUNT(DISTINCT crop)            AS n_crops,
            COUNT(DISTINCT market)          AS n_markets,
            {null_exprs}
        FROM feature_store
    """)
    stats = cur.fetchone()

    total_rows = stats[0]
    date_min   = stats[1]
    date_max   = stats[2]
    n_crops    = stats[3]
    n_markets  = stats[4]
    null_counts = dict(zip(_NUMERIC_COLS, stats[5:]))

    # Row counts per crop
    cur.execute("""
        SELECT crop, COUNT(*) AS n
        FROM feature_store
        GROUP BY crop
        ORDER BY crop
    """)
    crop_counts = cur.fetchall()

    # ── Step 2: export via COPY TO STDOUT ─────────────────────────────────
    print("Exporting CSV via COPY TO STDOUT...", flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    copy_sql = """
        COPY (
            SELECT *
            FROM feature_store
            ORDER BY crop, market, feature_date
        ) TO STDOUT WITH CSV HEADER
    """
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        cur.copy_expert(copy_sql, f)

    conn.commit()
    cur.close()
    conn.close()

    # ── Step 3: file size ─────────────────────────────────────────────────
    file_bytes = OUT_PATH.stat().st_size
    if file_bytes >= 1_048_576:
        file_size_str = f"{file_bytes / 1_048_576:.2f} MB"
    else:
        file_size_str = f"{file_bytes / 1024:.1f} KB"

    # ── Step 4: print summary ─────────────────────────────────────────────
    print()
    print("=" * 60)
    print("FEATURE STORE EXPORT SUMMARY")
    print("=" * 60)
    print(f"  Output file   : {OUT_PATH}")
    print(f"  File size     : {file_size_str}")
    print(f"  Total rows    : {total_rows:,}")
    print(f"  Date range    : {date_min} -> {date_max}")
    print(f"  Crops         : {n_crops}   Markets: {n_markets}")

    print()
    print("  Columns exported (all feature_store columns, ordered by crop/market/date)")

    print()
    print("  Row counts per crop:")
    for crop, n in crop_counts:
        print(f"    {crop:<15} {n:>6,}")

    high_null = [
        (col, cnt, round(cnt / total_rows * 100, 1))
        for col, cnt in null_counts.items()
        if total_rows > 0 and cnt / total_rows > 0.20
    ]
    print()
    if high_null:
        print("  High null rate columns (> 20%):")
        for col, cnt, pct in sorted(high_null, key=lambda x: -x[2]):
            print(f"    {col:<25} {pct:>5.1f}% null  ({cnt:,} of {total_rows:,})")
    else:
        print("  No columns above 20% null rate.")

    print()
    print(f"  Ready for Colab: {OUT_PATH.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
