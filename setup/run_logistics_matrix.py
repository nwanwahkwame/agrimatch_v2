"""
M8 - Build district_distances and logistics_costs using a single
psycopg2 connection and execute_values bulk inserts.

All rows are computed in Python and sent to Neon in large batches
(page_size=5000) to avoid per-session round-trip overhead.

Usage (from project root):
    python setup/run_logistics_matrix.py
"""

import math
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Constants ──────────────────────────────────────────────────────────────────

_NORTHERN = {"Northern", "Upper East", "Upper West", "Savannah", "North East", "Oti"}

_VEHICLE_SPECS = {
    "pickup":       12,
    "medium_truck": 20,
    "large_truck":  30,
}

_CARGO_TIERS = {
    "pickup":       [500, 1000, 1500],
    "medium_truck": [2000, 5000, 8000],
    "large_truck":  [8000, 15000, 20000],
}

DDL = [
    """
    CREATE TABLE IF NOT EXISTS district_distances (
        id               BIGSERIAL PRIMARY KEY,
        from_district_id BIGINT NOT NULL REFERENCES ghana_districts(id),
        to_district_id   BIGINT NOT NULL REFERENCES ghana_districts(id),
        straight_line_km NUMERIC(8,2),
        road_distance_km NUMERIC(8,2),
        road_quality     TEXT DEFAULT 'paved',
        road_factor      NUMERIC(4,2) DEFAULT 1.3,
        CONSTRAINT uq_district_distances_pair
            UNIQUE (from_district_id, to_district_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_district_distances_from ON district_distances (from_district_id)",
    """
    CREATE TABLE IF NOT EXISTS logistics_costs (
        id                  BIGSERIAL PRIMARY KEY,
        from_district_id    BIGINT NOT NULL REFERENCES ghana_districts(id),
        to_district_id      BIGINT NOT NULL REFERENCES ghana_districts(id),
        vehicle_type        TEXT NOT NULL,
        cargo_kg            NUMERIC(10,2),
        base_cost_ghs       NUMERIC(10,2),
        total_cost_ghs      NUMERIC(10,2),
        cost_per_kg_ghs     NUMERIC(8,4),
        diesel_price_used   NUMERIC(8,3),
        computed_at         TIMESTAMPTZ DEFAULT now(),
        CONSTRAINT uq_logistics_costs_key
            UNIQUE (from_district_id, to_district_id, vehicle_type, cargo_kg)
    )
    """,
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _costs(road_km, consumption, cargo_kg, diesel):
    fuel    = (road_km / 100) * consumption * diesel
    driver  = road_km * 0.50
    loading = cargo_kg * 0.02
    total   = fuel + driver + loading
    return round(fuel, 2), round(total, 2), round(total / cargo_kg, 4)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Step 0: tables ──────────────────────────────────────────────────────
    print("\nStep 0: Creating tables...", flush=True)
    for stmt in DDL:
        cur.execute(stmt)
    conn.commit()
    print("  Done.", flush=True)

    # ── Step 1: load districts ──────────────────────────────────────────────
    print("\nStep 1: Loading districts...", flush=True)
    cur.execute("""
        SELECT id, region_name, centroid_lat, centroid_lon
        FROM ghana_districts
        WHERE centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL
    """)
    districts = cur.fetchall()
    print(f"  {len(districts)} districts loaded.", flush=True)

    # ── Step 2: compute all distance pairs in Python ────────────────────────
    print("\nStep 2: Computing distance matrix...", flush=True)
    dist_rows = []
    for d1 in districts:
        for d2 in districts:
            if d1[0] == d2[0]:
                continue
            sl = _haversine(float(d1[2]), float(d1[3]), float(d2[2]), float(d2[3]))
            if d1[1] == d2[1]:
                quality, factor = "mixed",   1.4
            elif d1[1] in _NORTHERN or d2[1] in _NORTHERN:
                quality, factor = "unpaved", 1.8
            else:
                quality, factor = "paved",   1.3
            dist_rows.append((
                d1[0], d2[0],
                round(sl, 2), round(sl * factor, 2),
                quality, factor,
            ))

    print(f"  {len(dist_rows):,} pairs computed. Inserting...", flush=True)
    execute_values(
        cur,
        """INSERT INTO district_distances
               (from_district_id, to_district_id,
                straight_line_km, road_distance_km,
                road_quality, road_factor)
           VALUES %s
           ON CONFLICT (from_district_id, to_district_id) DO NOTHING""",
        dist_rows,
        page_size=5000,
    )
    conn.commit()
    print(f"  Distance matrix done: {len(dist_rows):,} pairs.", flush=True)

    # ── Step 3: diesel price ────────────────────────────────────────────────
    print("\nStep 3: Getting diesel price...", flush=True)
    cur.execute("""
        SELECT price_ghs_per_litre FROM fuel_prices
        WHERE fuel_type = 'diesel'
        ORDER BY price_date DESC LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        print("ERROR: No diesel price found in fuel_prices")
        sys.exit(1)
    diesel = float(row[0])
    print(f"  Diesel: GHS {diesel:.3f}/L", flush=True)

    # ── Step 4: cost matrix in chunks of 10,000 distance rows ───────────────
    print("\nStep 4: Building cost matrix...", flush=True)
    total_cost = 0
    chunk = 10000

    for i in range(0, len(dist_rows), chunk):
        slice_ = dist_rows[i:i + chunk]
        cost_batch = []
        for from_id, to_id, _, road_km, _, _ in slice_:
            for vtype, tiers in _CARGO_TIERS.items():
                cons = _VEHICLE_SPECS[vtype]
                for cargo in tiers:
                    base, total, per_kg = _costs(float(road_km), cons, float(cargo), diesel)
                    cost_batch.append((from_id, to_id, vtype, cargo, base, total, per_kg, diesel))

        execute_values(
            cur,
            """INSERT INTO logistics_costs
                   (from_district_id, to_district_id,
                    vehicle_type, cargo_kg,
                    base_cost_ghs, total_cost_ghs,
                    cost_per_kg_ghs, diesel_price_used)
               VALUES %s
               ON CONFLICT (from_district_id, to_district_id, vehicle_type, cargo_kg)
               DO UPDATE SET
                   base_cost_ghs     = EXCLUDED.base_cost_ghs,
                   total_cost_ghs    = EXCLUDED.total_cost_ghs,
                   cost_per_kg_ghs   = EXCLUDED.cost_per_kg_ghs,
                   diesel_price_used = EXCLUDED.diesel_price_used,
                   computed_at       = now()""",
            cost_batch,
            page_size=5000,
        )
        conn.commit()
        total_cost += len(cost_batch)
        print(f"  {total_cost:,} / ~606,060 cost rows inserted...", flush=True)

    # ── Step 5: summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print(f"Distance pairs : {len(dist_rows):,}", flush=True)
    print(f"Cost rows      : {total_cost:,}", flush=True)

    cur.execute("SELECT id FROM ghana_districts WHERE district_name ILIKE 'Ejura%' LIMIT 1")
    ejura = cur.fetchone()
    cur.execute("SELECT id FROM ghana_districts WHERE district_name ILIKE 'Kumasi%' LIMIT 1")
    kumasi = cur.fetchone()
    cur.execute("SELECT id FROM ghana_districts WHERE district_name ILIKE 'Tamale%' LIMIT 1")
    tamale = cur.fetchone()
    cur.execute("SELECT id FROM ghana_districts WHERE district_name ILIKE '%Accra%' LIMIT 1")
    accra = cur.fetchone()

    print("\nSample routes (5000 kg, medium_truck):", flush=True)
    for label, frm, to in [("Ejura -> Kumasi", ejura, kumasi), ("Tamale -> Accra", tamale, accra)]:
        if frm and to:
            cur.execute("""
                SELECT total_cost_ghs, cost_per_kg_ghs FROM logistics_costs
                WHERE from_district_id = %s AND to_district_id = %s
                  AND vehicle_type = 'medium_truck' AND cargo_kg = 5000
            """, (frm[0], to[0]))
            r = cur.fetchone()
            if r:
                print(f"  {label}: GHS {r[0]:.2f} | {r[1]:.4f} GHS/kg", flush=True)

    cur.execute("""
        SELECT d1.district_name, d2.district_name,
               lc.vehicle_type, lc.cargo_kg, lc.cost_per_kg_ghs
        FROM logistics_costs lc
        JOIN ghana_districts d1 ON d1.id = lc.from_district_id
        JOIN ghana_districts d2 ON d2.id = lc.to_district_id
        ORDER BY lc.cost_per_kg_ghs DESC LIMIT 1
    """)
    exp = cur.fetchone()
    cur.execute("""
        SELECT d1.district_name, d2.district_name,
               lc.vehicle_type, lc.cargo_kg, lc.cost_per_kg_ghs
        FROM logistics_costs lc
        JOIN ghana_districts d1 ON d1.id = lc.from_district_id
        JOIN ghana_districts d2 ON d2.id = lc.to_district_id
        WHERE lc.cost_per_kg_ghs > 0
        ORDER BY lc.cost_per_kg_ghs ASC LIMIT 1
    """)
    cheap = cur.fetchone()

    if exp:
        print(f"Most expensive: {exp[0]} -> {exp[1]} ({exp[2]}, {int(exp[3])}kg) GHS {exp[4]:.4f}/kg", flush=True)
    if cheap:
        print(f"Cheapest      : {cheap[0]} -> {cheap[1]} ({cheap[2]}, {int(cheap[3])}kg) GHS {cheap[4]:.4f}/kg", flush=True)

    cur.close()
    conn.close()
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
