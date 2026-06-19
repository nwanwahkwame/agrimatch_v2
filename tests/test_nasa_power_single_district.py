"""
NASA POWER single-district smoke test.

Fetches January 2023 data for Kumasi Metropolitan, saves to nasa_power_daily,
and verifies the results with sanity checks.

Usage (from project root):
    python tests/test_nasa_power_single_district.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_session
from ingestion.climate.nasa_power_client import NASAPowerClient
from sqlalchemy import text

START = date(2023, 1, 1)
END   = date(2023, 1, 31)

print()
print("=" * 65)
print("NASA POWER single-district smoke test -- Kumasi")
print(f"Date range: {START} to {END}")
print("=" * 65)

# ── 1. Load district record ───────────────────────────────────────────────────

with get_session() as s:
    row = s.execute(text("""
        SELECT id, centroid_lat, centroid_lon
        FROM ghana_districts
        WHERE district_name ILIKE '%Kumasi%'
        LIMIT 1
    """)).first()

if row is None:
    print()
    print("FAIL -- 'Kumasi' not found in ghana_districts")
    sys.exit(1)

district_id  = row.id
centroid_lat = float(row.centroid_lat)
centroid_lon = float(row.centroid_lon)

print()
print(f"District      : Kumasi")
print(f"district_id   : {district_id}")
print(f"Centroid      : {centroid_lat:.4f} N, {centroid_lon:.4f} E")

# ── 2. Fetch and save ─────────────────────────────────────────────────────────

client = NASAPowerClient()

print()
print("Fetching NASA POWER data ...")

try:
    df = client.fetch_district(district_id, centroid_lat, centroid_lon, START, END)
    print(f"  Raw rows fetched : {len(df)}")

    inserted = client.save_to_database(df)
    print(f"  Rows inserted    : {inserted}")
except Exception as exc:
    print()
    print(f"FAIL -- fetch/save raised: {exc}")
    sys.exit(1)

# ── 3. Query nasa_power_daily ─────────────────────────────────────────────────

print()
print("Querying nasa_power_daily ...")

with get_session() as s:
    stats = s.execute(text("""
        SELECT
            COUNT(*)                          AS row_count,
            ROUND(AVG(temp_mean)::numeric, 2) AS avg_temp_mean,
            ROUND(AVG(temp_max)::numeric, 2)  AS avg_temp_max,
            ROUND(AVG(temp_min)::numeric, 2)  AS avg_temp_min,
            ROUND(AVG(solar_mj)::numeric, 3)  AS avg_solar_mj,
            ROUND(AVG(et0_mm)::numeric, 3)    AS avg_et0_mm,
            COUNT(*) FILTER (WHERE et0_mm IS NULL) AS nan_et0_count
        FROM nasa_power_daily
        WHERE district_id = :did
          AND obs_date BETWEEN :start AND :end
    """), {"did": district_id, "start": START, "end": END}).first()

    nan_dates = s.execute(text("""
        SELECT obs_date
        FROM nasa_power_daily
        WHERE district_id = :did
          AND obs_date BETWEEN :start AND :end
          AND et0_mm IS NULL
        ORDER BY obs_date
    """), {"did": district_id, "start": START, "end": END}).all()

row_count     = stats.row_count     or 0
avg_temp_mean = stats.avg_temp_mean
avg_temp_max  = stats.avg_temp_max
avg_temp_min  = stats.avg_temp_min
avg_solar_mj  = stats.avg_solar_mj
avg_et0_mm    = stats.avg_et0_mm
nan_et0_count = stats.nan_et0_count or 0

print()
print("Results:")
print(f"  Rows returned    : {row_count}  (expect 31)")
print(f"  Avg temp_mean    : {avg_temp_mean} C")
print(f"  Avg temp_max     : {avg_temp_max} C")
print(f"  Avg temp_min     : {avg_temp_min} C")
print(f"  Avg solar_mj     : {avg_solar_mj} MJ/m2/day")
print(f"  Avg et0_mm       : {avg_et0_mm} mm/day")
print(f"  NaN et0_mm count : {nan_et0_count}")

if nan_dates:
    print("  Dates with NaN et0_mm:")
    for r in nan_dates:
        print(f"    {r.obs_date}")

# ── 4. Sanity checks ──────────────────────────────────────────────────────────

print()
print("Sanity checks:")

checks = []

def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    checks.append(condition)

check(
    f"Row count == 31  (got {row_count})",
    row_count == 31,
)
check(
    f"20 <= temp_mean <= 35  (got {avg_temp_mean})",
    avg_temp_mean is not None and 20 <= float(avg_temp_mean) <= 35,
)
check(
    f"10 <= solar_mj <= 25  (got {avg_solar_mj})",
    avg_solar_mj is not None and 10 <= float(avg_solar_mj) <= 25,
)
check(
    f"3 <= et0_mm <= 7  (got {avg_et0_mm})",
    avg_et0_mm is not None and 3 <= float(avg_et0_mm) <= 7,
)
check(
    f"Zero NaN et0_mm  (got {nan_et0_count})",
    nan_et0_count == 0,
)

# ── 5. Overall result ─────────────────────────────────────────────────────────

print()
print("=" * 65)
if all(checks):
    print(f"OVERALL PASS -- {row_count} rows, {avg_et0_mm} mm/day avg ET0")
else:
    failed = sum(1 for c in checks if not c)
    print(f"OVERALL FAIL -- {failed} of {len(checks)} checks failed")
print()
