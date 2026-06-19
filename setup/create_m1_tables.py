"""
Create M1 price pipeline tables on the current DATABASE_URL.

Tables created:
  raw_prices, clean_prices, price_quarantine,
  ingestion_log, ghana_markets, crop_reference

These tables have no FK to ghana_districts, so they can be created
before load_districts.py runs. Run create_climate_tables.py afterward
(it needs ghana_districts to already exist).

Usage (from project root):
    python setup/create_m1_tables.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect

from db.connection import get_engine
from db.models import (
    Base,
    CleanPrice,
    CropReference,
    GhanaMarket,
    IngestionLog,
    PriceQuarantine,
    RawPrice,
)

M1_TABLES = [
    RawPrice,
    CleanPrice,
    PriceQuarantine,
    IngestionLog,
    GhanaMarket,
    CropReference,
]

engine = get_engine()

print("Creating M1 tables ...")
Base.metadata.create_all(
    engine,
    tables=[m.__table__ for m in M1_TABLES],
    checkfirst=True,
)
print("  Done.")

insp    = inspect(engine)
existing = set(insp.get_table_names())

print()
print(f"  {'Table':<28} Status")
print("  " + "-" * 40)
all_ok = True
for model in M1_TABLES:
    tname = model.__tablename__
    ok    = tname in existing
    print(f"  {tname:<28} {'OK' if ok else 'MISSING'}")
    if not ok:
        all_ok = False

print()
if all_ok:
    print("All M1 tables created successfully.")
else:
    print("ERROR: one or more tables are missing -- check output above.")
    sys.exit(1)
