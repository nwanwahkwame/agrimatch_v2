"""
Run the CHIRPS daily rainfall backfill in three phases matching
the AgriMatch crop data tiers.

WARNING: This downloads ~4MB per date. With ~6,400 missing dates
the total download is roughly 25GB and will take many hours.
Do not run unless you have time and a stable connection.

Usage (from project root):
    python setup/run_chirps_backfill.py

The script is fully restartable -- it skips dates already in
chirps_daily, so you can interrupt and resume at any time.
"""

import logging
import sys
from datetime import date, timedelta
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
logger = logging.getLogger(__name__)

PHASES = [
    (
        "Phase 1 -- Tier 1 history",
        date(2006, 1, 1),
        date(2018, 12, 31),
    ),
    (
        "Phase 2 -- Tier 3 + recent",
        date(2019, 1, 1),
        date(2022, 12, 31),
    ),
    (
        "Phase 3 -- 2023 to end of price data",
        date(2023, 1, 1),
        date(2023, 7, 15),
    ),
]

DELAY_SECONDS = 2  # pause between downloads to avoid hammering CHIRPS server


# ── Helpers ───────────────────────────────────────────────────────────────────

def count_dates_in_range(start: date, end: date) -> int:
    return (end - start).days + 1


def count_ingested_in_range(start: date, end: date) -> int:
    with get_session() as s:
        return s.execute(text("""
            SELECT COUNT(DISTINCT obs_date)
            FROM chirps_daily
            WHERE obs_date BETWEEN :start AND :end
        """), {"start": start, "end": end}).scalar() or 0


def total_rows() -> int:
    with get_session() as s:
        return s.execute(text("SELECT COUNT(*) FROM chirps_daily")).scalar() or 0


def db_summary() -> dict:
    with get_session() as s:
        row = s.execute(text("""
            SELECT
                COUNT(*)                        AS total_rows,
                MIN(obs_date)                   AS date_min,
                MAX(obs_date)                   AS date_max,
                ROUND(AVG(daily_count), 1)      AS avg_districts
            FROM (
                SELECT obs_date, COUNT(*) AS daily_count
                FROM chirps_daily
                GROUP BY obs_date
            ) sub
        """)).first()
    return {
        "total_rows":     row.total_rows or 0,
        "date_min":       row.date_min,
        "date_max":       row.date_max,
        "avg_districts":  row.avg_districts,
    }


# ── Pre-run estimate ──────────────────────────────────────────────────────────

print()
print("=" * 70)
print("CHIRPS BACKFILL  --  AgriMatch M2")
print("=" * 70)
print()
print("Calculating missing dates ...")
print()

total_missing = 0
for label, start, end in PHASES:
    total  = count_dates_in_range(start, end)
    done   = count_ingested_in_range(start, end)
    need   = total - done
    total_missing += need
    print(f"  {label}")
    print(f"    {start} to {end}  |  {total} dates total  |  {done} already ingested  |  {need} to download")

est_gb = total_missing * 4 / 1024
print()
print(f"Estimated download: {total_missing} dates x ~4MB = ~{est_gb:.1f} GB")
print()
print(f"2-second pause between downloads.")
print(f"429/503 responses trigger a 60-second wait and one retry.")
print()

if total_missing == 0:
    print("Nothing to download -- all dates already ingested.")
    sys.exit(0)

# ── Phase loop ────────────────────────────────────────────────────────────────

client = CHIRPSClient()
cumulative_attempted = 0
cumulative_succeeded = 0
all_failed: list[date] = []

for phase_num, (label, start, end) in enumerate(PHASES, 1):
    need = count_ingested_in_range(start, end)
    total_in_phase = count_dates_in_range(start, end)
    if need == total_in_phase:
        print()
        print(f"[Phase {phase_num}] {label} -- fully ingested, skipping.")
        continue

    print()
    print("=" * 70)
    print(f"[Phase {phase_num}] {label}")
    print(f"  {start} to {end}")
    print("=" * 70)

    result = client.run_backfill(start, end, delay_seconds=DELAY_SECONDS)

    cumulative_attempted += result["dates_attempted"]
    cumulative_succeeded += result["dates_succeeded"]
    all_failed.extend(result["failed_dates"])

    rows_now = total_rows()

    print()
    print(f"  Phase {phase_num} result:")
    print(f"    Dates attempted  : {result['dates_attempted']}")
    print(f"    Dates succeeded  : {result['dates_succeeded']}")
    print(f"    Dates failed     : {result['dates_failed']}")
    if result["failed_dates"]:
        for fd in sorted(result["failed_dates"]):
            print(f"      - {fd}")
    print()
    print(f"  Cumulative after phase {phase_num}:")
    print(f"    Total attempted  : {cumulative_attempted}")
    print(f"    Total succeeded  : {cumulative_succeeded}")
    print(f"    Total failed     : {len(all_failed)}")
    print(f"    Rows in DB now   : {rows_now:,}")

# ── Final summary ─────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

info = db_summary()
print(f"  Total rows in chirps_daily : {info['total_rows']:,}")
print(f"  Date range covered         : {info['date_min']} to {info['date_max']}")
print(f"  Avg districts per day      : {info['avg_districts']}")
print(f"  Dates attempted (this run) : {cumulative_attempted}")
print(f"  Dates succeeded            : {cumulative_succeeded}")
print(f"  Dates failed               : {len(all_failed)}")

if all_failed:
    print()
    print("  Failed dates -- re-run individually with:")
    print("    from ingestion.climate.chirps_client import CHIRPSClient")
    print("    from datetime import date")
    print("    CHIRPSClient().run(date(YYYY, MM, DD))")
    print()
    for fd in sorted(all_failed):
        print(f"    {fd}")

print()
if not all_failed:
    print("COMPLETE -- all phases ingested successfully.")
else:
    print(f"COMPLETE WITH ERRORS -- {len(all_failed)} dates failed. See list above.")
