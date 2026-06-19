"""
Compute SPI baselines from chirps_daily and populate spi_baselines.

For each (district_id, calendar_month) pair, calculates:
  - baseline_mean_mm : mean daily rainfall across all years for that month
  - baseline_std_mm  : standard deviation of daily rainfall for that month
  - years_of_data    : number of distinct years contributing

These baselines are later used to compute SPI-30 in climate_indicators.

Usage (from project root):
    python setup/compute_spi_baselines.py
"""

import os
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_SQL_INSERT = """
INSERT INTO spi_baselines
    (district_id, calendar_month, baseline_mean_mm, baseline_std_mm, years_of_data)
WITH rolling AS (
    SELECT
        district_id,
        obs_date,
        EXTRACT(MONTH FROM obs_date)::integer AS calendar_month,
        SUM(COALESCE(mean_rainfall_mm, 0)) OVER (
            PARTITION BY district_id ORDER BY obs_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS rain_30day
    FROM chirps_daily
)
SELECT
    district_id,
    calendar_month,
    ROUND(AVG(rain_30day)::numeric, 3)                       AS baseline_mean_mm,
    ROUND(COALESCE(STDDEV(rain_30day), 0)::numeric, 3)       AS baseline_std_mm,
    COUNT(DISTINCT EXTRACT(YEAR FROM obs_date))::integer      AS years_of_data
FROM rolling
GROUP BY district_id, calendar_month
ON CONFLICT (district_id, calendar_month) DO UPDATE
    SET baseline_mean_mm = EXCLUDED.baseline_mean_mm,
        baseline_std_mm  = EXCLUDED.baseline_std_mm,
        years_of_data    = EXCLUDED.years_of_data,
        computed_at      = NOW()
"""

def compute_baselines() -> dict:
    """Run the SPI baseline upsert and return a result dict.

    Called by the scheduler for weekly refreshes as well as the CLI main().
    Opens its own DB connection from DATABASE_URL.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute(_SQL_INSERT)
        upserted = cur.rowcount
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM spi_baselines")
        total = cur.fetchone()[0]
    conn.close()

    return {
        "rows_upserted": upserted,
        "total_in_table": total,
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    print()
    print("Connecting to Railway PostgreSQL ...")
    conn = psycopg2.connect(
        db_url.replace("postgres://", "postgresql://", 1)
        if db_url.startswith("postgres://") else db_url
    )
    conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM chirps_daily WHERE mean_rainfall_mm IS NOT NULL")
        chirps_rows = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT district_id) FROM chirps_daily")
        districts = cur.fetchone()[0]
    conn.close()

    print(f"  Source: {chirps_rows:,} chirps_daily rows across {districts} districts")
    print()
    print("Computing SPI baselines ...")

    result = compute_baselines()

    print()
    print("=" * 50)
    print("SPI BASELINES COMPLETE")
    print("=" * 50)
    print(f"  Rows upserted  : {result['rows_upserted']:,}")
    print(f"  Total in table : {result['total_in_table']:,}")
    print(f"  Time taken     : {result['elapsed_s']:.1f}s")
    print()
    print("Next step:")
    print("  python setup/compute_climate_indicators.py")
    print()


if __name__ == "__main__":
    main()
