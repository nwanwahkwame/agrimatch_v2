"""
Load Ghana GADM level-2 district boundaries into PostgreSQL without PostGIS.

Creates ghana_districts as a plain table (no geometry column).
All pipeline scripts only use id, district_name, region_name,
centroid_lat, centroid_lon -- the geometry column is not needed.

Usage (from project root):
    python setup/load_districts_no_postgis.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
from sqlalchemy import text

from db.connection import get_engine, get_session

GPKG  = Path("data/gadm41_GHA.gpkg")
LAYER = "ADM_ADM_2"

RENAME = {
    "GID_2":     "district_code",
    "NAME_1":    "region_name",
    "NAME_2":    "district_name",
    "VARNAME_2": "variant_names",
    "TYPE_2":    "district_type",
    "HASC_2":    "hasc_code",
}

# ── 1. Load from GADM ─────────────────────────────────────────────────────────

print(f"Reading {LAYER} from {GPKG} ...")
gdf = gpd.read_file(str(GPKG), layer=LAYER, engine="pyogrio")
print(f"  {len(gdf)} districts loaded, CRS: {gdf.crs}")

gdf = gdf.rename(columns=RENAME)

# ── 2. Compute centroids (UTM 30N for accuracy, back to WGS84) ────────────────

gdf_utm = gdf.to_crs(epsg=32630)
centroids_wgs84 = gdf_utm.geometry.centroid.to_crs(epsg=4326)
gdf["centroid_lat"] = centroids_wgs84.y.round(6)
gdf["centroid_lon"] = centroids_wgs84.x.round(6)

# ── 3. Drop geometry -- plain DataFrame ───────────────────────────────────────

df = gdf[["district_code", "district_name", "region_name",
          "variant_names", "district_type", "hasc_code",
          "centroid_lat", "centroid_lon"]].copy()

# ── 4. Create table and insert ────────────────────────────────────────────────

engine = get_engine()

print("Creating ghana_districts table ...")
with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ghana_districts (
            id             BIGSERIAL PRIMARY KEY,
            district_code  TEXT,
            district_name  TEXT,
            region_name    TEXT,
            variant_names  TEXT,
            district_type  TEXT,
            hasc_code      TEXT,
            centroid_lat   DOUBLE PRECISION,
            centroid_lon   DOUBLE PRECISION
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_ghana_districts_district_name "
        "ON ghana_districts (district_name)"
    ))
    conn.commit()

print("Writing districts ...")
df.to_sql(
    name="ghana_districts",
    con=engine,
    if_exists="append",
    index=False,
    method="multi",
    chunksize=100,
)
print(f"  {len(df)} rows inserted")

# ── 5. Verify ─────────────────────────────────────────────────────────────────

with get_session() as s:
    total = s.execute(text("SELECT COUNT(*) FROM ghana_districts")).scalar()
    print(f"\nTotal districts in DB: {total}")

    print("\nDistricts per region:")
    rows = s.execute(text("""
        SELECT region_name, COUNT(*) AS districts
        FROM ghana_districts
        GROUP BY region_name
        ORDER BY districts DESC
    """)).all()
    print(f"  {'Region':<35} {'Districts':>9}")
    print("  " + "-" * 46)
    for r in rows:
        print(f"  {r.region_name:<35} {r.districts:>9}")

    print("\nSample (5 rows):")
    sample = s.execute(text("""
        SELECT district_name, region_name, centroid_lat, centroid_lon
        FROM ghana_districts
        ORDER BY region_name, district_name
        LIMIT 5
    """)).all()
    print(f"  {'District':<28} {'Region':<20} {'Lat':>10} {'Lon':>10}")
    print("  " + "-" * 72)
    for r in sample:
        print(f"  {r.district_name:<28} {r.region_name:<20} "
              f"{float(r.centroid_lat):>10.4f} {float(r.centroid_lon):>10.4f}")
