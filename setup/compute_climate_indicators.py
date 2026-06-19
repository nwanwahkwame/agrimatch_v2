"""
Populate climate_indicators from chirps_daily (SPI-30) and nasa_power_daily (ET0).

Processes 2006-01-01 to 2023-07-15 in monthly batches. Each month is computed
entirely in SQL (one INSERT ... WITH ... SELECT per month) for efficiency.

Handles three district categories:
  - Both CHIRPS + NASA POWER : full SPI and ET0 computation
  - CHIRPS only              : SPI computed, ET0 components set to 0
  - NASA POWER only          : ET0 computed, SPI set to 0, note='spi_unavailable'

Usage (from project root):
    python setup/compute_climate_indicators.py
"""

import calendar
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

START_DATE = date(2006, 1, 1)
END_DATE   = date(2023, 7, 15)

# ── SQL helpers ───────────────────────────────────────────────────────────────

_SQL_ADD_NOTE_COL = """
ALTER TABLE climate_indicators ADD COLUMN IF NOT EXISTS note TEXT
"""

_SQL_MONTH = """
INSERT INTO climate_indicators
    (indicator_date, district_id, spi_30day, et0_mm,
     csi_maize, csi_tomato, csi_onion, csi_cassava, csi_rice, csi_plantain,
     harvest_delay_days, flag_level, note)
WITH
-- 30-day rolling rainfall for the window period (extra 30 days before month)
chirps_win AS (
    SELECT district_id, obs_date,
           COALESCE(mean_rainfall_mm, 0.0) AS rain
    FROM chirps_daily
    WHERE obs_date >= %(window_start)s AND obs_date <= %(month_end)s
),
rolled AS (
    SELECT district_id, obs_date,
           SUM(rain) OVER (
               PARTITION BY district_id ORDER BY obs_date
               ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
           ) AS rain_30day
    FROM chirps_win
),
month_chirps AS (
    SELECT * FROM rolled
    WHERE obs_date >= %(month_start)s
),
-- NASA POWER for the month
nasa_month AS (
    SELECT district_id, obs_date, et0_mm
    FROM nasa_power_daily
    WHERE obs_date >= %(month_start)s AND obs_date <= %(month_end)s
),
-- CHIRPS-based districts (with or without NASA)
chirps_based AS (
    SELECT
        mc.district_id,
        mc.obs_date,
        CASE
            WHEN sb.baseline_std_mm IS NULL OR sb.baseline_std_mm = 0 THEN 0.0
            ELSE (mc.rain_30day - sb.baseline_mean_mm)
                 / sb.baseline_std_mm::double precision
        END AS spi_val,
        nm.et0_mm,
        CASE WHEN nm.et0_mm IS NULL THEN 'et0_unavailable'::text
             ELSE NULL END                             AS note
    FROM month_chirps mc
    LEFT JOIN spi_baselines sb
           ON sb.district_id   = mc.district_id
          AND sb.calendar_month = EXTRACT(MONTH FROM mc.obs_date)::int
    LEFT JOIN nasa_month nm
           ON nm.district_id = mc.district_id
          AND nm.obs_date    = mc.obs_date
),
-- NASA-only districts (CHIRPS missing for these 11 urban districts)
nasa_only AS (
    SELECT
        nm.district_id,
        nm.obs_date,
        0.0           AS spi_val,
        nm.et0_mm,
        'spi_unavailable'::text AS note
    FROM nasa_month nm
    LEFT JOIN month_chirps mc
           ON mc.district_id = nm.district_id
          AND mc.obs_date    = nm.obs_date
    WHERE mc.district_id IS NULL
),
combined AS (
    SELECT * FROM chirps_based
    UNION ALL
    SELECT * FROM nasa_only
),
-- Normalise both components to [0, 1]
normed AS (
    SELECT
        district_id, obs_date, note,
        ROUND(spi_val::numeric, 3)                          AS spi_30day,
        et0_mm,
        LEAST(GREATEST(-spi_val / 2.0, 0.0), 1.0)          AS spi_norm,
        CASE WHEN et0_mm IS NULL THEN 0.0
             ELSE LEAST(GREATEST((et0_mm - 2.0) / 8.0, 0.0), 1.0)
        END                                                  AS et0_norm
    FROM combined
),
-- CSI per crop
csi AS (
    SELECT
        district_id, obs_date, spi_30day, et0_mm, note,
        ROUND((0.65 * spi_norm + 0.35 * et0_norm)::numeric, 3) AS csi_maize,
        ROUND((0.50 * spi_norm + 0.50 * et0_norm)::numeric, 3) AS csi_tomato,
        ROUND((0.55 * spi_norm + 0.45 * et0_norm)::numeric, 3) AS csi_onion,
        ROUND((0.60 * spi_norm + 0.40 * et0_norm)::numeric, 3) AS csi_cassava,
        ROUND((0.70 * spi_norm + 0.30 * et0_norm)::numeric, 3) AS csi_rice,
        ROUND((0.60 * spi_norm + 0.40 * et0_norm)::numeric, 3) AS csi_plantain
    FROM normed
),
worst AS (
    SELECT *,
        GREATEST(csi_maize, csi_tomato, csi_onion,
                 csi_cassava, csi_rice, csi_plantain) AS worst_csi
    FROM csi
)
SELECT
    obs_date AS indicator_date,
    district_id,
    spi_30day,
    et0_mm,
    csi_maize, csi_tomato, csi_onion, csi_cassava, csi_rice, csi_plantain,
    CASE
        WHEN worst_csi < 0.30 THEN 0
        WHEN worst_csi < 0.55 THEN 3
        WHEN worst_csi < 0.75 THEN 9
        ELSE 18
    END AS harvest_delay_days,
    CASE
        WHEN worst_csi < 0.30 THEN 'normal'
        WHEN worst_csi < 0.55 THEN 'watch'
        WHEN worst_csi < 0.75 THEN 'warning'
        ELSE 'critical'
    END AS flag_level,
    note
FROM worst
ON CONFLICT (indicator_date, district_id) DO UPDATE
    SET spi_30day          = EXCLUDED.spi_30day,
        et0_mm             = EXCLUDED.et0_mm,
        csi_maize          = EXCLUDED.csi_maize,
        csi_tomato         = EXCLUDED.csi_tomato,
        csi_onion          = EXCLUDED.csi_onion,
        csi_cassava        = EXCLUDED.csi_cassava,
        csi_rice           = EXCLUDED.csi_rice,
        csi_plantain       = EXCLUDED.csi_plantain,
        harvest_delay_days = EXCLUDED.harvest_delay_days,
        flag_level         = EXCLUDED.flag_level,
        note               = EXCLUDED.note
"""

_SQL_SUMMARY = """
SELECT
    COUNT(*)                                           AS total_rows,
    COUNT(DISTINCT district_id)                        AS districts,
    MIN(indicator_date)                                AS earliest,
    MAX(indicator_date)                                AS latest,
    COUNT(*) FILTER (WHERE flag_level = 'normal')      AS n_normal,
    COUNT(*) FILTER (WHERE flag_level = 'watch')       AS n_watch,
    COUNT(*) FILTER (WHERE flag_level = 'warning')     AS n_warning,
    COUNT(*) FILTER (WHERE flag_level = 'critical')    AS n_critical,
    ROUND(AVG(csi_maize)::numeric, 3)                  AS avg_csi_maize,
    ROUND(AVG(csi_tomato)::numeric, 3)                 AS avg_csi_tomato,
    ROUND(AVG(csi_onion)::numeric, 3)                  AS avg_csi_onion,
    ROUND(AVG(csi_cassava)::numeric, 3)                AS avg_csi_cassava,
    ROUND(AVG(csi_rice)::numeric, 3)                   AS avg_csi_rice,
    ROUND(AVG(csi_plantain)::numeric, 3)               AS avg_csi_plantain,
    COUNT(*) FILTER (WHERE note IS NOT NULL)            AS flagged_rows,
    COUNT(*) FILTER (WHERE note = 'spi_unavailable')   AS spi_unavailable,
    COUNT(*) FILTER (WHERE note = 'et0_unavailable')   AS et0_unavailable
FROM climate_indicators
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def connect(db_url):
    c = psycopg2.connect(db_url,
                         keepalives=1, keepalives_idle=60,
                         keepalives_interval=10, keepalives_count=5)
    c.autocommit = False
    return c


def month_bounds(year, month):
    """Return (first_day, last_day) for the given year/month, capped at END_DATE."""
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = min(date(year, month, last_day), END_DATE)
    return first, last


def iter_months(start, end):
    """Yield (month_start, month_end) from start to end inclusive."""
    y, m = start.year, start.month
    while True:
        ms, me = month_bounds(y, m)
        yield ms, me
        if me >= end:
            break
        m += 1
        if m > 12:
            m = 1
            y += 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print()
    print("Connecting to Railway PostgreSQL ...")
    conn = connect(db_url)

    # Verify prerequisites
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM spi_baselines")
        n_baselines = cur.fetchone()[0]
        if n_baselines == 0:
            print("ERROR: spi_baselines is empty -- run compute_spi_baselines.py first")
            sys.exit(1)
        print(f"  spi_baselines: {n_baselines} rows")

        cur.execute("SELECT COUNT(*) FROM chirps_daily")
        print(f"  chirps_daily : {cur.fetchone()[0]:,} rows")
        cur.execute("SELECT COUNT(*) FROM nasa_power_daily")
        print(f"  nasa_power_daily: {cur.fetchone()[0]:,} rows")

    # Add note column if absent
    with conn.cursor() as cur:
        cur.execute(_SQL_ADD_NOTE_COL)
    conn.commit()
    print("  note column ready")
    print()

    t0 = time.time()
    months_done   = 0
    total_upserted = 0

    for month_start, month_end in iter_months(START_DATE, END_DATE):
        window_start = month_start - timedelta(days=30)

        with conn.cursor() as cur:
            cur.execute(_SQL_MONTH, {
                "window_start": window_start,
                "month_start":  month_start,
                "month_end":    month_end,
            })
            upserted = max(cur.rowcount, 0)
        conn.commit()

        months_done    += 1
        total_upserted += upserted
        label = f"{month_start.year}-{month_start.month:02d}"
        print(f"  Processed {label}: {upserted:,} indicators", flush=True)

    elapsed = time.time() - t0

    # Final summary
    with conn.cursor() as cur:
        cur.execute(_SQL_SUMMARY)
        r = cur.fetchone()
    conn.close()

    (total_rows, districts, earliest, latest,
     n_normal, n_watch, n_warning, n_critical,
     avg_maize, avg_tomato, avg_onion, avg_cassava, avg_rice, avg_plantain,
     flagged, spi_unavail, et0_unavail) = r

    print()
    print("=" * 60)
    print("CLIMATE INDICATORS COMPLETE")
    print("=" * 60)
    print(f"  Total rows        : {total_rows:,}")
    print(f"  Districts covered : {districts}")
    print(f"  Date range        : {earliest} to {latest}")
    print(f"  Months processed  : {months_done}")
    print(f"  Time taken        : {elapsed:.1f}s")
    print()
    print("  Flag level distribution:")
    print(f"    normal   : {n_normal:>10,}")
    print(f"    watch    : {n_watch:>10,}")
    print(f"    warning  : {n_warning:>10,}")
    print(f"    critical : {n_critical:>10,}")
    print()
    print("  Average CSI per crop:")
    print(f"    maize    : {avg_maize}")
    print(f"    tomato   : {avg_tomato}")
    print(f"    onion    : {avg_onion}")
    print(f"    cassava  : {avg_cassava}")
    print(f"    rice     : {avg_rice}")
    print(f"    plantain : {avg_plantain}")
    print()
    if flagged:
        print(f"  Data quality notes:")
        print(f"    spi_unavailable : {spi_unavail:,} rows (NASA POWER only districts)")
        print(f"    et0_unavailable : {et0_unavail:,} rows (CHIRPS only districts)")
    print()


if __name__ == "__main__":
    main()
