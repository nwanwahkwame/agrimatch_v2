"""
Create feature_store table and populate it via pure-SQL feature engineering.

Everything runs on the DB server:
  - Window functions for lag and rolling stats (no data transfer)
  - LATERAL joins for climate and fuel as-of lookups (uses server indexes)
  - Zero rows transferred to Python during computation

Usage (from project root):
    python setup/run_feature_engineering.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

# ── DDL ───────────────────────────────────────────────────────────────────────

DDL = [
    """
    CREATE TABLE IF NOT EXISTS feature_store (
        id                 BIGSERIAL PRIMARY KEY,
        feature_date       DATE        NOT NULL,
        market             TEXT        NOT NULL,
        crop               TEXT        NOT NULL,
        price_ghs          NUMERIC(10,2),
        lag_7d             NUMERIC(10,2),
        lag_14d            NUMERIC(10,2),
        lag_30d            NUMERIC(10,2),
        lag_90d            NUMERIC(10,2),
        rolling_mean_30d   NUMERIC(10,2),
        rolling_std_30d    NUMERIC(10,2),
        rolling_mean_90d   NUMERIC(10,2),
        rolling_min_30d    NUMERIC(10,2),
        rolling_max_30d    NUMERIC(10,2),
        price_momentum_7d  NUMERIC(10,4),
        price_momentum_30d NUMERIC(10,4),
        sin_week           NUMERIC(8,6),
        cos_week           NUMERIC(8,6),
        sin_month          NUMERIC(8,6),
        cos_month          NUMERIC(8,6),
        spi_30day          NUMERIC(6,3),
        et0_mm             NUMERIC(8,3),
        csi_value          NUMERIC(5,3),
        fuel_price_diesel  NUMERIC(8,3),
        district_id        BIGINT REFERENCES ghana_districts(id),
        CONSTRAINT uq_feature_store_date_market_crop
            UNIQUE (feature_date, market, crop)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_feature_store_crop_market_date
        ON feature_store (crop, market, feature_date)
    """,
    # Index that makes the LATERAL climate join fast
    """
    CREATE INDEX IF NOT EXISTS ix_climate_indicators_district_date
        ON climate_indicators (district_id, indicator_date DESC)
    """,
]

# ── Feature SQL (runs entirely on the DB server) ──────────────────────────────

FEATURE_SQL = """
WITH
deduped AS (
    -- Collapse any duplicate (date, market, crop) by averaging
    SELECT
        price_date,
        market,
        crop,
        AVG(price_ghs) AS price_ghs
    FROM clean_prices
    WHERE price_ghs IS NOT NULL
    GROUP BY price_date, market, crop
),
windowed AS (
    SELECT
        d.price_date,
        d.market,
        d.crop,
        d.price_ghs,
        LAG(d.price_ghs,  7) OVER w AS lag_7d,
        LAG(d.price_ghs, 14) OVER w AS lag_14d,
        LAG(d.price_ghs, 30) OVER w AS lag_30d,
        LAG(d.price_ghs, 90) OVER w AS lag_90d,
        AVG(d.price_ghs)     OVER w30 AS rolling_mean_30d,
        STDDEV(d.price_ghs)  OVER w30 AS rolling_std_30d,
        AVG(d.price_ghs)     OVER w90 AS rolling_mean_90d,
        MIN(d.price_ghs)     OVER w30 AS rolling_min_30d,
        MAX(d.price_ghs)     OVER w30 AS rolling_max_30d,
        EXTRACT(WEEK  FROM d.price_date)::NUMERIC AS week_num,
        EXTRACT(MONTH FROM d.price_date)::NUMERIC AS month_num,
        gm.district_id
    FROM deduped d
    LEFT JOIN ghana_markets gm ON gm.canonical_name = d.market
    WINDOW
        w   AS (PARTITION BY d.crop, d.market ORDER BY d.price_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
        w30 AS (PARTITION BY d.crop, d.market ORDER BY d.price_date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW),
        w90 AS (PARTITION BY d.crop, d.market ORDER BY d.price_date
                ROWS BETWEEN 89 PRECEDING AND CURRENT ROW)
),
enriched AS (
    SELECT
        *,
        CASE WHEN lag_7d  IS NOT NULL AND lag_7d  <> 0
             THEN (price_ghs - lag_7d)  / lag_7d  END AS price_momentum_7d,
        CASE WHEN lag_30d IS NOT NULL AND lag_30d <> 0
             THEN (price_ghs - lag_30d) / lag_30d END AS price_momentum_30d,
        SIN(2 * PI() * week_num  / 52) AS sin_week,
        COS(2 * PI() * week_num  / 52) AS cos_week,
        SIN(2 * PI() * month_num / 12) AS sin_month,
        COS(2 * PI() * month_num / 12) AS cos_month
    FROM windowed
    WHERE NOT (
        lag_7d IS NULL AND lag_14d IS NULL
        AND lag_30d IS NULL AND lag_90d IS NULL
    )
)
INSERT INTO feature_store (
    feature_date, market, crop, price_ghs,
    lag_7d, lag_14d, lag_30d, lag_90d,
    rolling_mean_30d, rolling_std_30d, rolling_mean_90d,
    rolling_min_30d,  rolling_max_30d,
    price_momentum_7d, price_momentum_30d,
    sin_week, cos_week, sin_month, cos_month,
    spi_30day, et0_mm, csi_value,
    fuel_price_diesel, district_id
)
SELECT
    e.price_date AS feature_date,
    e.market,
    e.crop,
    e.price_ghs,
    e.lag_7d,  e.lag_14d, e.lag_30d, e.lag_90d,
    e.rolling_mean_30d, e.rolling_std_30d, e.rolling_mean_90d,
    e.rolling_min_30d,  e.rolling_max_30d,
    e.price_momentum_7d, e.price_momentum_30d,
    e.sin_week, e.cos_week, e.sin_month, e.cos_month,
    ci.spi_30day,
    ci.et0_mm,
    CASE e.crop
        WHEN 'maize'    THEN ci.csi_maize
        WHEN 'tomato'   THEN ci.csi_tomato
        WHEN 'onion'    THEN ci.csi_onion
        WHEN 'cassava'  THEN ci.csi_cassava
        WHEN 'rice'     THEN ci.csi_rice
        WHEN 'plantain' THEN ci.csi_plantain
        ELSE NULL
    END AS csi_value,
    fp.price_ghs_per_litre AS fuel_price_diesel,
    e.district_id
FROM enriched e
LEFT JOIN LATERAL (
    SELECT spi_30day, et0_mm,
           csi_maize, csi_tomato, csi_onion,
           csi_cassava, csi_rice, csi_plantain
    FROM climate_indicators
    WHERE district_id = e.district_id
      AND indicator_date <= e.price_date
    ORDER BY indicator_date DESC
    LIMIT 1
) ci ON TRUE
LEFT JOIN LATERAL (
    SELECT price_ghs_per_litre
    FROM fuel_prices
    WHERE fuel_type = 'diesel'
      AND price_date <= e.price_date
    ORDER BY price_date DESC
    LIMIT 1
) fp ON TRUE
ON CONFLICT (feature_date, market, crop) DO UPDATE SET
    price_ghs          = EXCLUDED.price_ghs,
    lag_7d             = EXCLUDED.lag_7d,
    lag_14d            = EXCLUDED.lag_14d,
    lag_30d            = EXCLUDED.lag_30d,
    lag_90d            = EXCLUDED.lag_90d,
    rolling_mean_30d   = EXCLUDED.rolling_mean_30d,
    rolling_std_30d    = EXCLUDED.rolling_std_30d,
    rolling_mean_90d   = EXCLUDED.rolling_mean_90d,
    rolling_min_30d    = EXCLUDED.rolling_min_30d,
    rolling_max_30d    = EXCLUDED.rolling_max_30d,
    price_momentum_7d  = EXCLUDED.price_momentum_7d,
    price_momentum_30d = EXCLUDED.price_momentum_30d,
    sin_week           = EXCLUDED.sin_week,
    cos_week           = EXCLUDED.cos_week,
    sin_month          = EXCLUDED.sin_month,
    cos_month          = EXCLUDED.cos_month,
    spi_30day          = EXCLUDED.spi_30day,
    et0_mm             = EXCLUDED.et0_mm,
    csi_value          = EXCLUDED.csi_value,
    fuel_price_diesel  = EXCLUDED.fuel_price_diesel,
    district_id        = EXCLUDED.district_id
"""


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print()
    print("Step 1: Creating feature_store table and indexes ...")
    with conn.cursor() as cur:
        for stmt in DDL:
            cur.execute(stmt)
    conn.commit()
    print("  Done.")

    print()
    print("Step 2: Running feature engineering on DB server ...")
    print("  (window functions + LATERAL joins -- no data transfer)")
    with conn.cursor() as cur:
        cur.execute(FEATURE_SQL)
        rows_upserted = cur.rowcount
    conn.commit()
    print(f"  Done. Rows upserted: {rows_upserted:,}")

    print()
    print("=" * 62)
    print("FINAL SUMMARY")
    print("=" * 62)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM feature_store")
        total = cur.fetchone()[0]

        cur.execute("SELECT MIN(feature_date), MAX(feature_date) FROM feature_store")
        mn, mx = cur.fetchone()

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT crop, market FROM feature_store
            ) x
        """)
        pairs = cur.fetchone()[0]

        print(f"  feature_store rows    : {total:,}")
        print(f"  Unique crop-market pairs : {pairs}")
        print(f"  Date range            : {mn} to {mx}")
        print()

        print(f"  {'Crop':<14} {'Rows':>8}  {'Has CSI':>8}  {'Has Climate':>12}")
        print("  " + "-" * 46)
        cur.execute("""
            SELECT
                crop,
                COUNT(*) AS n,
                COUNT(csi_value) AS has_csi,
                COUNT(spi_30day) AS has_climate
            FROM feature_store
            GROUP BY crop
            ORDER BY n DESC
        """)
        for row in cur.fetchall():
            print(f"  {row[0]:<14} {row[1]:>8,}  {row[2]:>8,}  {row[3]:>12,}")

        print()
        print("  Sample row -- maize / Kumasi (most recent):")
        print("  " + "-" * 58)
        cur.execute("""
            SELECT feature_date, price_ghs,
                   lag_7d, lag_30d, lag_90d,
                   rolling_mean_30d, rolling_std_30d,
                   ROUND(price_momentum_7d::numeric,  4),
                   ROUND(price_momentum_30d::numeric, 4),
                   ROUND(sin_week::numeric, 4),
                   ROUND(sin_month::numeric, 4),
                   spi_30day, fuel_price_diesel
            FROM feature_store
            WHERE crop = 'maize' AND market = 'Kumasi'
            ORDER BY feature_date DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            labels = [
                "feature_date", "price_ghs",
                "lag_7d", "lag_30d", "lag_90d",
                "rolling_mean_30d", "rolling_std_30d",
                "price_momentum_7d", "price_momentum_30d",
                "sin_week", "sin_month",
                "spi_30day", "fuel_price_diesel",
            ]
            for label, val in zip(labels, row):
                print(f"  {label:<22} : {val}")
        else:
            print("  (no maize/Kumasi rows found)")

    conn.close()
    print()


if __name__ == "__main__":
    main()
