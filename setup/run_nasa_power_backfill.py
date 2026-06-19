"""
Run the NASA POWER daily climate backfill in three phases matching
the AgriMatch crop data tiers.

Fetches T2M, T2M_MAX, T2M_MIN, solar radiation, humidity, wind speed,
and computed ET0 (FAO Penman-Monteith) for all 260 Ghana districts.

Usage (from project root):
    python setup/run_nasa_power_backfill.py

The script is fully restartable -- it skips districts that already have
complete data for each phase date range. Interrupt and resume at any time.

Rate: ~0.5s between API calls. 260 districts x 18 year-long chunks
= ~4,680 API calls. Estimated runtime: 40-60 minutes.
"""

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_session
from ingestion.climate.nasa_power_client import NASAPowerClient
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

FULL_START = date(2006, 1, 1)
FULL_END   = date(2023, 7, 15)


# ── Helpers ───────────────────────────────────────────────────────────────────

def count_existing_combos(start: date, end: date) -> int:
    """Count district-date rows already in nasa_power_daily for a range."""
    with get_session() as s:
        return s.execute(text("""
            SELECT COUNT(*)
            FROM nasa_power_daily
            WHERE obs_date BETWEEN :start AND :end
        """), {"start": start, "end": end}).scalar() or 0


def count_complete_districts(start: date, end: date) -> int:
    """Districts with a full row for every date in the range."""
    expected = (end - start).days + 1
    with get_session() as s:
        return s.execute(text("""
            SELECT COUNT(*)
            FROM (
                SELECT district_id
                FROM nasa_power_daily
                WHERE obs_date BETWEEN :start AND :end
                GROUP BY district_id
                HAVING COUNT(DISTINCT obs_date) >= :expected
            ) complete
        """), {"start": start, "end": end, "expected": expected}).scalar() or 0


def total_rows_in_db() -> int:
    with get_session() as s:
        return s.execute(text("SELECT COUNT(*) FROM nasa_power_daily")).scalar() or 0


def fetch_district_names(district_ids: list[int]) -> dict[int, str]:
    """Return {id: district_name} for a list of district ids."""
    if not district_ids:
        return {}
    with get_session() as s:
        rows = s.execute(text("""
            SELECT id, district_name
            FROM ghana_districts
            WHERE id = ANY(:ids)
        """), {"ids": district_ids}).all()
    return {r.id: r.district_name for r in rows}


def db_summary() -> dict:
    with get_session() as s:
        row = s.execute(text("""
            SELECT
                COUNT(*)       AS total_rows,
                MIN(obs_date)  AS date_min,
                MAX(obs_date)  AS date_max
            FROM nasa_power_daily
        """)).first()
    return {
        "total_rows": row.total_rows or 0,
        "date_min":   row.date_min,
        "date_max":   row.date_max,
    }


def csi_readiness_summary() -> dict:
    """
    Count districts with complete data in both CHIRPS and NASA POWER
    for the full backfill range -- these are ready for CSI computation.
    """
    expected_days = (FULL_END - FULL_START).days + 1

    with get_session() as s:
        # Districts with complete NASA POWER coverage
        nasa_complete = s.execute(text("""
            SELECT district_id
            FROM nasa_power_daily
            WHERE obs_date BETWEEN :start AND :end
            GROUP BY district_id
            HAVING COUNT(DISTINCT obs_date) >= :expected
        """), {"start": FULL_START, "end": FULL_END, "expected": expected_days}).all()

        # Districts with complete CHIRPS coverage
        chirps_complete = s.execute(text("""
            SELECT district_id
            FROM chirps_daily
            WHERE obs_date BETWEEN :start AND :end
            GROUP BY district_id
            HAVING COUNT(DISTINCT obs_date) >= :expected
        """), {"start": FULL_START, "end": FULL_END, "expected": expected_days}).all()

    nasa_ids   = {r.district_id for r in nasa_complete}
    chirps_ids = {r.district_id for r in chirps_complete}
    both_ids   = nasa_ids & chirps_ids

    return {
        "nasa_complete":  len(nasa_ids),
        "chirps_complete": len(chirps_ids),
        "both_complete":  len(both_ids),
    }


# ── Pre-run summary ───────────────────────────────────────────────────────────

print()
print("=" * 70)
print("NASA POWER BACKFILL  --  AgriMatch M2")
print("=" * 70)
print()
print("Checking existing data in nasa_power_daily ...")
print()

for label, start, end in PHASES:
    expected_combos = ((end - start).days + 1) * 260
    existing        = count_existing_combos(start, end)
    complete_dists  = count_complete_districts(start, end)
    pct             = existing / expected_combos * 100 if expected_combos else 0
    print(f"  {label}")
    print(
        f"    {start} to {end}  |  "
        f"{existing:,} / {expected_combos:,} rows ({pct:.1f}%)  |  "
        f"{complete_dists} / 260 districts complete"
    )

print()

# ── Phase loop ────────────────────────────────────────────────────────────────

client = NASAPowerClient()
cumulative_inserted = 0
all_failed_ids: list[int] = []

for phase_num, (label, start, end) in enumerate(PHASES, 1):
    complete_before = count_complete_districts(start, end)
    if complete_before >= 260:
        print()
        print(f"[Phase {phase_num}] {label} -- all 260 districts complete, skipping.")
        continue

    print()
    print("=" * 70)
    print(f"[Phase {phase_num}] {label}")
    print(f"  {start} to {end}")
    print("=" * 70)

    result = client.run_backfill(start, end)

    cumulative_inserted += result["total_rows_inserted"]
    all_failed_ids.extend(result["failed_district_ids"])

    failed_names = fetch_district_names(result["failed_district_ids"])
    rows_now = total_rows_in_db()

    print()
    print(f"  Phase {phase_num} result:")
    print(f"    Districts total      : {result['districts_total']}")
    print(f"    Districts fetched    : {result['districts_fetched']}")
    print(f"    Districts succeeded  : {result.get('districts_succeeded', 'n/a')}")
    print(f"    Districts failed     : {result['districts_failed']}")
    if failed_names:
        print(f"    Failed districts:")
        for did, dname in sorted(failed_names.items(), key=lambda x: x[1]):
            print(f"      - [{did}] {dname}")
    print(f"    Rows inserted        : {result['total_rows_inserted']:,}")
    print()
    print(f"  Cumulative after phase {phase_num}:")
    print(f"    Total inserted this run : {cumulative_inserted:,}")
    print(f"    Total rows in DB now    : {rows_now:,}")

# ── Final summary ─────────────────────────────────────────────────────────────

print()
print("=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

info = db_summary()
print(f"  Total rows in nasa_power_daily : {info['total_rows']:,}")
print(f"  Date range covered             : {info['date_min']} to {info['date_max']}")
print(f"  Rows inserted this run         : {cumulative_inserted:,}")
print(f"  Districts failed this run      : {len(all_failed_ids)}")

print()
expected_days = (FULL_END - FULL_START).days + 1
nasa_complete = count_complete_districts(FULL_START, FULL_END)
print(f"  Districts with full NASA POWER coverage ({FULL_START} to {FULL_END}):")
print(f"    {nasa_complete} / 260")

print()
csi = csi_readiness_summary()
print(f"  CSI readiness (both CHIRPS + NASA POWER complete):")
print(f"    CHIRPS complete  : {csi['chirps_complete']} / 260")
print(f"    NASA POWER       : {csi['nasa_complete']} / 260")
print(f"    Both complete    : {csi['both_complete']} of 260 districts have both")
print(
    f"    CHIRPS and NASA POWER data and are ready for CSI computation"
)

if all_failed_ids:
    failed_names = fetch_district_names(list(set(all_failed_ids)))
    print()
    print(f"  Failed districts -- retry individually with:")
    print(f"    from ingestion.climate.nasa_power_client import NASAPowerClient")
    print(f"    from datetime import date")
    print(f"    NASAPowerClient().run_backfill(date(YYYY, MM, DD), date(YYYY, MM, DD))")
    print()
    for did in sorted(set(all_failed_ids)):
        dname = failed_names.get(did, f"id={did}")
        print(f"    [{did}] {dname}")

print()
if not all_failed_ids:
    print("COMPLETE -- all phases ingested successfully.")
else:
    print(f"COMPLETE WITH ERRORS -- {len(set(all_failed_ids))} districts failed. See list above.")
