"""
Create the four M2 climate tables in PostgreSQL.

  chirps_daily       -- daily CHIRPS rainfall per district
  nasa_power_daily   -- daily NASA POWER weather vars per district
  spi_baselines      -- 30-day rainfall baseline stats per district/month
  climate_indicators -- computed SPI, ET0, CSI, flags per district/day

Idempotent: uses CREATE TABLE IF NOT EXISTS (checkfirst=True default).

Usage (from project root):
    python setup/create_climate_tables.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import Table, inspect, text

from db.connection import get_engine
from db.models import (
    Base,
    ChirpsDaily,
    ClimateIndicator,
    NasaPowerDaily,
    SpiBaseline,
)

CLIMATE_TABLES = [
    ChirpsDaily,
    NasaPowerDaily,
    SpiBaseline,
    ClimateIndicator,
]

engine = get_engine()

# ghana_districts was created by geopandas to_postgis(), not by our ORM, so
# SQLAlchemy's metadata has no entry for it. Reflecting it here lets create_all
# resolve the FK references without erroring on an unknown table.
Table("ghana_districts", Base.metadata, autoload_with=engine)

print("Creating climate tables ...")
Base.metadata.create_all(
    engine,
    tables=[m.__table__ for m in CLIMATE_TABLES],
)
print("  Done.")

# ── Verification ──────────────────────────────────────────────────────────────

insp = inspect(engine)
existing = set(insp.get_table_names())

print()
print(f"  {'Table':<28} Status")
print("  " + "-" * 42)
all_ok = True
for model in CLIMATE_TABLES:
    tname = model.__tablename__
    ok = tname in existing
    print(f"  {tname:<28} {'OK' if ok else 'MISSING'}")
    if not ok:
        all_ok = False

print()
print("Indexes per table:")
with engine.connect() as conn:
    for model in CLIMATE_TABLES:
        tname = model.__tablename__
        rows = conn.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = :t
            ORDER BY indexname
        """), {"t": tname}).all()
        print(f"  {tname}:")
        for r in rows:
            print(f"    {r.indexname}")

print()
if all_ok:
    print("All four climate tables created successfully.")
else:
    print("ERROR: one or more tables are missing -- check output above.")
    sys.exit(1)
