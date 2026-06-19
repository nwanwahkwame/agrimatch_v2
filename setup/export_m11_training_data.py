"""
Export climate_indicators training data for the harvest delay classifier.

Joins climate_indicators to ghana_districts, computes lag features via
window functions, and saves to data/m11_training_data.csv.

Usage (from project root):
    python setup/export_m11_training_data.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

OUT_PATH = Path(__file__).parent.parent / "data" / "m11_training_data.csv"

_EXPORT_SQL = """
    SELECT
        ci.indicator_date,
        ci.district_id,
        gd.region_name,
        ci.spi_30day,
        ci.et0_mm,
        ci.csi_maize,
        ci.csi_tomato,
        ci.csi_onion,
        ci.csi_cassava,
        ci.csi_rice,
        ci.csi_plantain,
        ci.flag_level,
        ci.harvest_delay_days,
        EXTRACT(MONTH FROM ci.indicator_date) AS month,
        EXTRACT(DOY FROM ci.indicator_date) / 365.0 AS day_of_year_norm,
        LAG(ci.csi_maize, 1) OVER (
            PARTITION BY ci.district_id
            ORDER BY ci.indicator_date) AS csi_maize_lag1,
        LAG(ci.spi_30day, 1) OVER (
            PARTITION BY ci.district_id
            ORDER BY ci.indicator_date) AS spi_lag1,
        LAG(ci.spi_30day, 3) OVER (
            PARTITION BY ci.district_id
            ORDER BY ci.indicator_date) AS spi_lag3
    FROM climate_indicators ci
    JOIN ghana_districts gd ON ci.district_id = gd.id
    ORDER BY ci.district_id, ci.indicator_date
"""

_NULL_COLS = [
    "spi_30day", "et0_mm",
    "csi_maize", "csi_tomato", "csi_onion",
    "csi_cassava", "csi_rice", "csi_plantain",
    "flag_level", "harvest_delay_days",
]


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    cur  = conn.cursor()

    # ── Summary stats ─────────────────────────────────────────────────────────
    print("Fetching summary stats...", flush=True)

    null_exprs = ",\n        ".join(
        f"COUNT(*) - COUNT({c}) AS null_{c}" for c in _NULL_COLS
    )
    cur.execute(f"""
        SELECT
            COUNT(*)                    AS total_rows,
            MIN(ci.indicator_date)      AS date_min,
            MAX(ci.indicator_date)      AS date_max,
            {null_exprs}
        FROM climate_indicators ci
    """)
    stats      = cur.fetchone()
    total_rows = stats[0]
    date_min   = stats[1]
    date_max   = stats[2]
    null_counts = dict(zip(_NULL_COLS, stats[3:]))

    # Lag columns will always have some nulls (first rows of each partition)
    # Fetch count separately so we can check the lag null rate post-export
    cur.execute("""
        SELECT COUNT(*) FROM climate_indicators
    """)
    ci_total = cur.fetchone()[0]

    # flag_level distribution
    cur.execute("""
        SELECT flag_level, COUNT(*) AS n
        FROM climate_indicators
        GROUP BY flag_level
        ORDER BY flag_level
    """)
    flag_dist = cur.fetchall()

    # harvest_delay_days distribution
    cur.execute("""
        SELECT harvest_delay_days, COUNT(*) AS n
        FROM climate_indicators
        GROUP BY harvest_delay_days
        ORDER BY harvest_delay_days
    """)
    delay_dist = cur.fetchall()

    # ── Export via COPY TO STDOUT ─────────────────────────────────────────────
    print("Exporting CSV...", flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    copy_sql = f"COPY ({_EXPORT_SQL}) TO STDOUT WITH CSV HEADER"
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        cur.copy_expert(copy_sql, f)

    conn.commit()
    cur.close()
    conn.close()

    # ── File size ─────────────────────────────────────────────────────────────
    file_bytes = OUT_PATH.stat().st_size
    if file_bytes >= 1_048_576:
        size_str = f"{file_bytes / 1_048_576:.2f} MB"
    else:
        size_str = f"{file_bytes / 1024:.1f} KB"

    # ── Print summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("M11 TRAINING DATA EXPORT SUMMARY")
    print("=" * 60)
    print(f"  Output file : {OUT_PATH}")
    print(f"  File size   : {size_str}")
    print(f"  Total rows  : {total_rows:,}")
    print(f"  Date range  : {date_min} -> {date_max}")

    print()
    print("  flag_level distribution:")
    for level, n in flag_dist:
        pct = n / total_rows * 100 if total_rows else 0
        print(f"    {str(level):<8} {n:>6,}  ({pct:.1f}%)")

    print()
    print("  harvest_delay_days distribution:")
    for days, n in delay_dist:
        pct = n / total_rows * 100 if total_rows else 0
        print(f"    {str(days):<8} {n:>6,}  ({pct:.1f}%)")

    print()
    high_null = [
        (col, cnt, cnt / total_rows * 100)
        for col, cnt in null_counts.items()
        if total_rows > 0 and cnt / total_rows > 0.05
    ]
    if high_null:
        print("  Null rates above 5%:")
        for col, cnt, pct in sorted(high_null, key=lambda x: -x[2]):
            print(f"    {col:<25} {pct:>5.1f}%  ({cnt:,} nulls)")
    else:
        print("  No base columns above 5% null rate.")

    print()
    print(f"  Lag columns (nulls expected for first rows per district):")
    print(f"    csi_maize_lag1, spi_lag1  -- 1 row null per district")
    print(f"    spi_lag3                  -- 3 rows null per district")

    print()
    print(f"  Ready for Colab: {OUT_PATH.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
