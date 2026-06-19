"""
Load Ghana GADM level-2 district boundaries into PostgreSQL.

Reads data/gadm41_GHA.gpkg, cleans columns, computes district centroids,
writes to the ghana_districts table, then matches markets in ghana_markets
to their districts.

Usage (from project root):
    python setup/load_districts.py
"""

import sys
from pathlib import Path

# Allow imports from project root when run as a plain script
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
from sqlalchemy import text

from db.connection import get_engine, get_session

GPKG = Path("data/gadm41_GHA.gpkg")
LAYER = "ADM_ADM_2"

RENAME = {
    "GID_2":    "district_code",
    "NAME_1":   "region_name",
    "NAME_2":   "district_name",
    "VARNAME_2": "variant_names",
    "TYPE_2":   "district_type",
    "HASC_2":   "hasc_code",
}

KEEP = [
    "district_code", "district_name", "region_name",
    "variant_names", "district_type", "hasc_code",
    "centroid_lat", "centroid_lon", "geometry",
]


# ── 1. Load and clean ─────────────────────────────────────────────────────────

print(f"Reading {LAYER} from {GPKG} ...")
gdf = gpd.read_file(str(GPKG), layer=LAYER, engine="pyogrio")
print(f"  {len(gdf)} districts loaded, CRS: {gdf.crs}")

gdf = gdf.rename(columns=RENAME)

# ── 2. Centroids (project to UTM 30N for accuracy, extract WGS84 coords) ─────

gdf_utm = gdf.to_crs(epsg=32630)
centroids_wgs84 = gdf_utm.geometry.centroid.to_crs(epsg=4326)
gdf["centroid_lat"] = centroids_wgs84.y.round(6)
gdf["centroid_lon"] = centroids_wgs84.x.round(6)

# ── 3. Keep only required columns, ensure WGS84 ───────────────────────────────

gdf = gdf[KEEP].copy()
gdf = gdf.set_crs(epsg=4326, allow_override=True)

# ── 4. Write to PostgreSQL ────────────────────────────────────────────────────

engine = get_engine()

print("Enabling PostGIS extension ...")
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    conn.commit()

print("Writing ghana_districts table ...")
gdf.to_postgis(
    name="ghana_districts",
    con=engine,
    if_exists="replace",
    index=False,
    dtype={"geometry": None},
)
print(f"  ghana_districts written ({len(gdf)} rows)")

# ── 5. Confirmation queries ───────────────────────────────────────────────────

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

    print("\nSample districts (5 rows):")
    sample = s.execute(text("""
        SELECT district_name, region_name, centroid_lat, centroid_lon
        FROM ghana_districts
        ORDER BY region_name, district_name
        LIMIT 5
    """)).all()
    print(f"  {'District':<28} {'Region':<20} {'Lat':>10} {'Lon':>10}")
    print("  " + "-" * 72)
    for r in sample:
        print(f"  {r.district_name:<28} {r.region_name:<20} {float(r.centroid_lat):>10.4f} {float(r.centroid_lon):>10.4f}")

# ── 6. Match ghana_markets to districts ──────────────────────────────────────

print("\nMatching ghana_markets to districts ...")

with get_session() as s:
    markets = s.execute(text(
        "SELECT id, canonical_name FROM ghana_markets"
    )).all()

    if not markets:
        print("  ghana_markets table is empty -- no markets to match.")
    else:
        districts = s.execute(text(
            "SELECT id, district_name, variant_names FROM ghana_districts"
        )).all()

        # Build lookup: lowercased name -> district id
        district_lookup: dict[str, int] = {}
        for d in districts:
            district_lookup[d.district_name.lower()] = d.id
            if d.variant_names:
                for variant in d.variant_names.split("|"):
                    v = variant.strip().lower()
                    if v:
                        district_lookup[v] = d.id

        matched = 0
        unmatched = []

        for m in markets:
            key = (m.canonical_name or "").strip().lower()
            district_id = district_lookup.get(key)
            if district_id:
                s.execute(text(
                    "UPDATE ghana_markets SET district_id = :did WHERE id = :mid"
                ), {"did": district_id, "mid": m.id})
                matched += 1
            else:
                unmatched.append(m.canonical_name)

        print(f"  Matched {matched} of {len(markets)} markets to districts")
        if unmatched:
            print(f"  Could not match ({len(unmatched)}):")
            for name in unmatched:
                print(f"    - {name}")
        else:
            print("  All markets matched successfully")
