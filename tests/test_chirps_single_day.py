"""
Smoke test: download, process, and verify CHIRPS data for 2023-01-15.

Usage (from project root):
    python tests/test_chirps_single_day.py
"""

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_session
from ingestion.climate.chirps_client import CHIRPSClient
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
    datefmt="%H:%M:%S",
)

TARGET = date(2023, 1, 15)
MIN_DISTRICTS = 200

print("=" * 65)
print(f"CHIRPS single-day smoke test -- {TARGET}")
print("=" * 65)

# ── 1. Run ingestion ──────────────────────────────────────────────

client = CHIRPSClient()
try:
    summary = client.run(TARGET)
except Exception as exc:
    print(f"\nFAIL -- client.run() raised: {exc}")
    sys.exit(1)

print()
print("Run summary:")
print(f"  Districts with data : {summary['districts_with_data']}")
print(f"  Total cells         : {summary['total_cells']}")
print(f"  Rainfall range (mm) : {summary['mm_min']:.2f} - {summary['mm_max']:.2f}")
print(f"  Rows inserted       : {summary['rows_inserted']}")

# ── 2. Query results ──────────────────────────────────────────────

print()
print("Querying chirps_daily for", TARGET, "...")

with get_session() as s:
    stats = s.execute(text("""
        SELECT
            COUNT(*)                          AS district_count,
            MIN(mean_rainfall_mm)             AS mm_min,
            MAX(mean_rainfall_mm)             AS mm_max,
            ROUND(AVG(mean_rainfall_mm), 3)   AS mm_avg,
            SUM(cell_count)                   AS total_cells
        FROM chirps_daily
        WHERE obs_date = :d
    """), {"d": TARGET}).first()

    top5 = s.execute(text("""
        SELECT d.district_name, c.mean_rainfall_mm, c.cell_count
        FROM chirps_daily c
        JOIN ghana_districts d ON d.id = c.district_id
        WHERE c.obs_date = :d
        ORDER BY c.mean_rainfall_mm DESC
        LIMIT 5
    """), {"d": TARGET}).all()

    bot5 = s.execute(text("""
        SELECT d.district_name, c.mean_rainfall_mm, c.cell_count
        FROM chirps_daily c
        JOIN ghana_districts d ON d.id = c.district_id
        WHERE c.obs_date = :d
        ORDER BY c.mean_rainfall_mm ASC
        LIMIT 5
    """), {"d": TARGET}).all()

    zero_cells = s.execute(text("""
        SELECT d.district_name
        FROM chirps_daily c
        JOIN ghana_districts d ON d.id = c.district_id
        WHERE c.obs_date = :d AND c.cell_count = 0
        ORDER BY d.district_name
    """), {"d": TARGET}).all()

district_count = stats.district_count
mm_min  = float(stats.mm_min)  if stats.mm_min  is not None else None
mm_max  = float(stats.mm_max)  if stats.mm_max  is not None else None
mm_avg  = float(stats.mm_avg)  if stats.mm_avg  is not None else None

print()
print(f"  Districts in DB     : {district_count}")
print(f"  Rainfall min (mm)   : {mm_min:.3f}" if mm_min is not None else "  Rainfall min (mm)   : --")
print(f"  Rainfall max (mm)   : {mm_max:.3f}" if mm_max is not None else "  Rainfall max (mm)   : --")
print(f"  Rainfall avg (mm)   : {mm_avg:.3f}" if mm_avg is not None else "  Rainfall avg (mm)   : --")

print()
print("Top 5 districts by rainfall:")
print(f"  {'District':<32} {'mm':>7}  cells")
print("  " + "-" * 48)
for r in top5:
    print(f"  {r.district_name:<32} {float(r.mean_rainfall_mm):>7.3f}  {r.cell_count}")

print()
print("Bottom 5 districts by rainfall:")
print(f"  {'District':<32} {'mm':>7}  cells")
print("  " + "-" * 48)
for r in bot5:
    print(f"  {r.district_name:<32} {float(r.mean_rainfall_mm):>7.3f}  {r.cell_count}")

if zero_cells:
    print()
    print(f"Districts with zero cells ({len(zero_cells)}):")
    for r in zero_cells:
        print(f"  {r.district_name}")

# ── 3. Coverage warning ───────────────────────────────────────────

print()
if district_count < MIN_DISTRICTS:
    print(
        f"WARNING: only {district_count} districts have data "
        f"(expected >= {MIN_DISTRICTS}). "
        "Spatial join may have missed districts -- check sjoin predicate."
    )

# ── 4. Pass / Fail ────────────────────────────────────────────────

print()
print("=" * 65)
if district_count == 0:
    print(f"FAIL -- no rows found in chirps_daily for {TARGET}")
    sys.exit(1)
elif mm_min is None or mm_max is None:
    print("FAIL -- rainfall stats returned NULL")
    sys.exit(1)
elif mm_min < 0:
    print(f"FAIL -- negative rainfall value found: {mm_min:.3f} mm")
    sys.exit(1)
else:
    coverage_note = (
        f" (coverage warning: {district_count} < {MIN_DISTRICTS})"
        if district_count < MIN_DISTRICTS else ""
    )
    print(f"PASS -- {district_count} districts, {mm_avg:.3f} mm avg{coverage_note}")
