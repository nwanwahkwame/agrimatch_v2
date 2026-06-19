"""
M8 - Logistics Cost Matrix for AgriMatch.

Builds two matrices from ghana_districts centroids:
  1. district_distances  - Haversine + road-factor adjusted distances
  2. logistics_costs     - fuel + driver + loading costs per vehicle/cargo tier

Exposes get_delivery_cost() for M14 landed-cost lookups.
"""

import logging
import math
from typing import Optional

from sqlalchemy import text

from db.connection import get_session
from ingestion.fuel_scraper import FuelScraper

logger = logging.getLogger(__name__)

_NORTHERN_REGIONS = {
    "Northern", "Upper East", "Upper West", "Savannah", "North East", "Oti"
}

_VEHICLE_SPECS = {
    "pickup":       {"consumption": 12, "capacity": 1500},
    "medium_truck": {"consumption": 20, "capacity": 8000},
    "large_truck":  {"consumption": 30, "capacity": 20000},
}

_CARGO_TIERS = {
    "pickup":       [500, 1000, 1500],
    "medium_truck": [2000, 5000, 8000],
    "large_truck":  [8000, 15000, 20000],
}

_INSERT_DISTANCE = """
    INSERT INTO district_distances (
        from_district_id, to_district_id,
        straight_line_km, road_distance_km,
        road_quality, road_factor
    ) VALUES (
        :from_id, :to_id,
        :straight_km, :road_km,
        :road_quality, :road_factor
    )
    ON CONFLICT (from_district_id, to_district_id) DO NOTHING
"""

_UPSERT_COST = """
    INSERT INTO logistics_costs (
        from_district_id, to_district_id,
        vehicle_type, cargo_kg,
        base_cost_ghs, total_cost_ghs,
        cost_per_kg_ghs, diesel_price_used
    ) VALUES (
        :from_id, :to_id,
        :vehicle_type, :cargo_kg,
        :base_cost, :total_cost,
        :cost_per_kg, :diesel_price
    )
    ON CONFLICT (from_district_id, to_district_id, vehicle_type, cargo_kg) DO UPDATE SET
        base_cost_ghs     = EXCLUDED.base_cost_ghs,
        total_cost_ghs    = EXCLUDED.total_cost_ghs,
        cost_per_kg_ghs   = EXCLUDED.cost_per_kg_ghs,
        diesel_price_used = EXCLUDED.diesel_price_used,
        computed_at       = now()
"""


class LogisticsCostModel:

    # ── Haversine ──────────────────────────────────────────────────────────────

    def compute_haversine(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Standard Haversine formula. Returns distance in km."""
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ── Distance matrix ────────────────────────────────────────────────────────

    def build_distance_matrix(self) -> int:
        """Compute straight-line and road distances for all district pairs.

        Assigns road_quality and road_factor:
          - same region      -> mixed,   1.4
          - either northern  -> unpaved, 1.8
          - otherwise        -> paved,   1.3

        Inserts in batches of 1000, skips self-to-self pairs.
        Returns total pairs written.
        """
        with get_session() as db:
            rows = db.execute(
                text("""
                    SELECT id, region_name, centroid_lat, centroid_lon
                    FROM ghana_districts
                    WHERE centroid_lat IS NOT NULL AND centroid_lon IS NOT NULL
                """)
            ).fetchall()

        districts = [
            {"id": r[0], "region": r[1], "lat": float(r[2]), "lon": float(r[3])}
            for r in rows
        ]
        print(f"  Loaded {len(districts)} districts with coordinates", flush=True)

        batch = []
        total = 0

        for d1 in districts:
            for d2 in districts:
                if d1["id"] == d2["id"]:
                    continue

                sl_km = self.compute_haversine(d1["lat"], d1["lon"], d2["lat"], d2["lon"])

                same_region = d1["region"] == d2["region"]
                northern = (
                    d1["region"] in _NORTHERN_REGIONS
                    or d2["region"] in _NORTHERN_REGIONS
                )

                if same_region:
                    road_quality, road_factor = "mixed", 1.4
                elif northern:
                    road_quality, road_factor = "unpaved", 1.8
                else:
                    road_quality, road_factor = "paved", 1.3

                batch.append({
                    "from_id": d1["id"],
                    "to_id": d2["id"],
                    "straight_km": round(sl_km, 2),
                    "road_km": round(sl_km * road_factor, 2),
                    "road_quality": road_quality,
                    "road_factor": road_factor,
                })

                if len(batch) >= 5000:
                    with get_session() as db:
                        db.execute(text(_INSERT_DISTANCE), batch)
                    total += len(batch)
                    batch = []
                    if total % 10000 == 0:
                        print(f"  {total:,} distance pairs written...", flush=True)

        if batch:
            with get_session() as db:
                db.execute(text(_INSERT_DISTANCE), batch)
            total += len(batch)

        return total

    # ── Vehicle cost computation ───────────────────────────────────────────────

    def compute_vehicle_costs(
        self,
        distance_km: float,
        vehicle_type: str,
        cargo_kg: float,
        diesel_price: float,
    ) -> dict:
        """Compute fuel, driver, and loading costs for a single trip.

        Returns base_cost_ghs (fuel only), total_cost_ghs, cost_per_kg_ghs.
        """
        spec = _VEHICLE_SPECS[vehicle_type]
        fuel_cost = (distance_km / 100) * spec["consumption"] * diesel_price
        driver_cost = distance_km * 0.50
        loading_cost = cargo_kg * 0.02
        total_cost = fuel_cost + driver_cost + loading_cost
        return {
            "base_cost_ghs": round(fuel_cost, 2),
            "total_cost_ghs": round(total_cost, 2),
            "cost_per_kg_ghs": round(total_cost / cargo_kg, 4),
        }

    # ── Cost matrix ───────────────────────────────────────────────────────────

    def build_cost_matrix(self) -> int:
        """Compute logistics costs for all district pairs x vehicle/cargo tiers.

        Fetches current diesel price, loads all distance rows, then for each
        pair inserts 9 rows (3 vehicle types x 3 cargo tiers).
        Uses ON CONFLICT DO UPDATE so costs refresh when diesel price changes.
        Returns total rows written.
        """
        prices = FuelScraper().get_latest_prices()
        diesel_price = prices.get("diesel")
        if diesel_price is None:
            raise RuntimeError("No diesel price found in fuel_prices table")
        print(f"  Diesel price: GHS {diesel_price:.3f}/L", flush=True)

        with get_session() as db:
            dist_rows = db.execute(
                text("SELECT from_district_id, to_district_id, road_distance_km FROM district_distances")
            ).fetchall()

        print(f"  Loaded {len(dist_rows):,} distance pairs", flush=True)

        batch = []
        total = 0

        for from_id, to_id, road_km in dist_rows:
            road_km_f = float(road_km)
            for vehicle_type, tiers in _CARGO_TIERS.items():
                for cargo_kg in tiers:
                    costs = self.compute_vehicle_costs(
                        road_km_f, vehicle_type, float(cargo_kg), diesel_price
                    )
                    batch.append({
                        "from_id": from_id,
                        "to_id": to_id,
                        "vehicle_type": vehicle_type,
                        "cargo_kg": cargo_kg,
                        "base_cost": costs["base_cost_ghs"],
                        "total_cost": costs["total_cost_ghs"],
                        "cost_per_kg": costs["cost_per_kg_ghs"],
                        "diesel_price": diesel_price,
                    })

                    if len(batch) >= 5000:
                        with get_session() as db:
                            db.execute(text(_UPSERT_COST), batch)
                        total += len(batch)
                        batch = []
                        if total % 50000 == 0:
                            print(f"  {total:,} cost rows written...", flush=True)

        if batch:
            with get_session() as db:
                db.execute(text(_UPSERT_COST), batch)
            total += len(batch)

        return total

    # ── Delivery cost lookup ───────────────────────────────────────────────────

    def get_delivery_cost(
        self,
        from_district_id: int,
        to_district_id: int,
        cargo_kg: float,
    ) -> Optional[dict]:
        """Return landed cost for the best-fit vehicle type and cargo tier.

        Vehicle selection: <=1500 kg -> pickup, <=8000 kg -> medium_truck,
        >8000 kg -> large_truck. Tier is the closest stored cargo_kg.
        Returns None if no cost row exists for the pair.
        """
        if cargo_kg <= 1500:
            vehicle_type = "pickup"
            tiers = [500, 1000, 1500]
        elif cargo_kg <= 8000:
            vehicle_type = "medium_truck"
            tiers = [2000, 5000, 8000]
        else:
            vehicle_type = "large_truck"
            tiers = [8000, 15000, 20000]

        closest_tier = min(tiers, key=lambda t: abs(t - cargo_kg))

        with get_session() as db:
            row = db.execute(
                text("""
                    SELECT base_cost_ghs, total_cost_ghs, cost_per_kg_ghs,
                           diesel_price_used, cargo_kg, vehicle_type
                    FROM logistics_costs
                    WHERE from_district_id = :from_id
                      AND to_district_id   = :to_id
                      AND vehicle_type     = :vtype
                      AND cargo_kg         = :cargo
                """),
                {
                    "from_id": from_district_id,
                    "to_id": to_district_id,
                    "vtype": vehicle_type,
                    "cargo": closest_tier,
                },
            ).fetchone()

        if row is None:
            return None

        return {
            "from_district_id": from_district_id,
            "to_district_id": to_district_id,
            "vehicle_type": vehicle_type,
            "cargo_kg_tier": int(closest_tier),
            "base_cost_ghs": float(row[0]),
            "total_cost_ghs": float(row[1]),
            "cost_per_kg_ghs": float(row[2]),
            "diesel_price_used": float(row[3]),
        }

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self) -> dict:
        """Build distance matrix then cost matrix. Print summary."""
        print("Step 1: Building distance matrix...")
        n_dist = self.build_distance_matrix()
        print(f"  Done. {n_dist:,} distance pairs.")

        print()
        print("Step 2: Building cost matrix...")
        n_cost = self.build_cost_matrix()
        print(f"  Done. {n_cost:,} cost rows.")

        print()
        print("=" * 60)
        print(f"Total distance pairs : {n_dist:,}")
        print(f"Total cost rows      : {n_cost:,}")

        # Look up sample district IDs
        with get_session() as db:
            ejura = db.execute(
                text("SELECT id FROM ghana_districts WHERE district_name ILIKE 'Ejura%' LIMIT 1")
            ).fetchone()
            kumasi = db.execute(
                text("SELECT id FROM ghana_districts WHERE district_name ILIKE 'Kumasi%' LIMIT 1")
            ).fetchone()
            tamale = db.execute(
                text("SELECT id FROM ghana_districts WHERE district_name ILIKE 'Tamale%' LIMIT 1")
            ).fetchone()
            accra = db.execute(
                text("SELECT id FROM ghana_districts WHERE district_name ILIKE '%Accra%' LIMIT 1")
            ).fetchone()

        print()
        print("Sample routes (5000 kg, medium truck):")
        print("  " + "-" * 45)
        if ejura and kumasi:
            c = self.get_delivery_cost(ejura[0], kumasi[0], 5000)
            if c:
                print(
                    f"  Ejura -> Kumasi    : GHS {c['total_cost_ghs']:>8.2f} "
                    f"| {c['cost_per_kg_ghs']:.4f} GHS/kg"
                )
        if tamale and accra:
            c = self.get_delivery_cost(tamale[0], accra[0], 5000)
            if c:
                print(
                    f"  Tamale -> Accra    : GHS {c['total_cost_ghs']:>8.2f} "
                    f"| {c['cost_per_kg_ghs']:.4f} GHS/kg"
                )

        print()
        with get_session() as db:
            most_exp = db.execute(
                text("""
                    SELECT d1.district_name, d2.district_name,
                           lc.vehicle_type, lc.cargo_kg, lc.cost_per_kg_ghs
                    FROM logistics_costs lc
                    JOIN ghana_districts d1 ON d1.id = lc.from_district_id
                    JOIN ghana_districts d2 ON d2.id = lc.to_district_id
                    ORDER BY lc.cost_per_kg_ghs DESC LIMIT 1
                """)
            ).fetchone()
            cheapest = db.execute(
                text("""
                    SELECT d1.district_name, d2.district_name,
                           lc.vehicle_type, lc.cargo_kg, lc.cost_per_kg_ghs
                    FROM logistics_costs lc
                    JOIN ghana_districts d1 ON d1.id = lc.from_district_id
                    JOIN ghana_districts d2 ON d2.id = lc.to_district_id
                    WHERE lc.cost_per_kg_ghs > 0
                    ORDER BY lc.cost_per_kg_ghs ASC LIMIT 1
                """)
            ).fetchone()

        if most_exp:
            print(
                f"Most expensive: {most_exp[0]} -> {most_exp[1]} "
                f"({most_exp[2]}, {int(most_exp[3])} kg) "
                f"GHS {most_exp[4]:.4f}/kg"
            )
        if cheapest:
            print(
                f"Cheapest      : {cheapest[0]} -> {cheapest[1]} "
                f"({cheapest[2]}, {int(cheapest[3])} kg) "
                f"GHS {cheapest[4]:.4f}/kg"
            )
        print()

        return {"distance_pairs": n_dist, "cost_rows": n_cost}
