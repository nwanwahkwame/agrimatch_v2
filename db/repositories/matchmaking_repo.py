from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


class MatchmakingRepo:

    @staticmethod
    def get_median_price(db: Session, crop: str):
        """Return the median price row; caller applies safe_float conversion."""
        row = db.execute(text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_forecast_ghs)
                   AS median_price
            FROM farmer_declarations
            WHERE crop   = :crop
              AND status = 'active'
              AND price_forecast_ghs IS NOT NULL
        """), {"crop": crop}).fetchone()
        return row

    @staticmethod
    def get_road_km(db: Session, from_did: int, to_did: int) -> float:
        row = db.execute(text("""
            SELECT road_distance_km
            FROM district_distances
            WHERE from_district_id = :from_id
              AND to_district_id   = :to_id
            LIMIT 1
        """), {"from_id": from_did, "to_id": to_did}).fetchone()
        return float(row.road_distance_km) if row else 0.0

    @staticmethod
    def get_declaration_for_scoring(db: Session, declaration_id: int):
        return db.execute(text("""
            SELECT id, crop, quantity_kg, district_id,
                   harvest_date, adjusted_harvest_date,
                   price_forecast_ghs, csi_flag
            FROM farmer_declarations
            WHERE id = :did
        """), {"did": declaration_id}).fetchone()

    @staticmethod
    def search_listings(
        db: Session,
        sql_params: dict,
        exclude_csi: bool = False,
        min_qty: Optional[float] = None,
        max_price: Optional[float] = None,
    ):
        """Execute the main buyer search query.

        Optional filter clauses are built here so no SQL fragments escape the
        repository layer. sql_params is not mutated — extra binds use a copy.
        """
        extra: list = []
        params = dict(sql_params)   # work on a copy; do not mutate caller's dict
        if exclude_csi:
            extra.append("AND fd.csi_flag NOT IN ('warning', 'critical')")
        if min_qty is not None:
            extra.append("AND fd.quantity_kg >= :min_qty")
            params["min_qty"] = min_qty
        if max_price is not None:
            extra.append("AND (fd.price_forecast_ghs IS NULL OR fd.price_forecast_ghs <= :max_price)")
            params["max_price"] = max_price
        clause_str = "\n".join(extra)

        return db.execute(text(f"""
            SELECT fd.id, fd.farmer_id, fd.quantity_kg, fd.district_id,
                   fd.harvest_date, fd.adjusted_harvest_date,
                   fd.price_forecast_ghs, fd.csi_flag,
                   f.full_name AS farmer_name,
                   gd.district_name, gd.region_name,
                   COALESCE(dd.road_distance_km, 0) AS road_distance_km,
                   COALESCE(lc.total_cost_ghs,   0) AS delivery_cost_ghs,
                   COALESCE(lc.cost_per_kg_ghs,  0) AS cost_per_kg_ghs
            FROM farmer_declarations fd
            JOIN farmers f          ON f.id  = fd.farmer_id
            JOIN ghana_districts gd ON gd.id = fd.district_id
            LEFT JOIN district_distances dd
                   ON dd.from_district_id = fd.district_id
                  AND dd.to_district_id   = :buyer_did
            LEFT JOIN logistics_costs lc
                   ON lc.from_district_id = fd.district_id
                  AND lc.to_district_id   = :buyer_did
                  AND lc.vehicle_type     = :logi_vtype
                  AND lc.cargo_kg         = :logi_cargo
            WHERE fd.crop   = :crop
              AND fd.status = 'active'
              AND fd.harvest_date BETWEEN :hfrom AND :hto
              {clause_str}
        """), params).fetchall()

    @staticmethod
    def get_buyer_district_name(db: Session, buyer_district_id: int) -> str:
        row = db.execute(
            text("SELECT district_name FROM ghana_districts WHERE id = :did LIMIT 1"),
            {"did": buyer_district_id},
        ).fetchone()
        return row[0] if row else str(buyer_district_id)

    @staticmethod
    def get_market_summary(db: Session, date_range: dict):
        return db.execute(text("""
            SELECT COUNT(*) AS listing_count,
                   COALESCE(SUM(quantity_kg), 0) AS total_supply_kg,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_forecast_ghs)
                       AS median_price,
                   MIN(price_forecast_ghs) AS min_price,
                   MAX(price_forecast_ghs) AS max_price
            FROM farmer_declarations
            WHERE crop   = :crop
              AND status = 'active'
              AND harvest_date BETWEEN :hfrom AND :hto
        """), date_range).fetchone()

    @staticmethod
    def get_csi_distribution(db: Session, date_range: dict):
        return db.execute(text("""
            SELECT COALESCE(csi_flag, 'normal') AS flag, COUNT(*) AS cnt
            FROM farmer_declarations
            WHERE crop   = :crop
              AND status = 'active'
              AND harvest_date BETWEEN :hfrom AND :hto
            GROUP BY flag
        """), date_range).fetchall()

    @staticmethod
    def get_regional_supply(db: Session, date_range: dict):
        return db.execute(text("""
            SELECT gd.region_name,
                   COUNT(*) AS listing_count,
                   COALESCE(SUM(fd.quantity_kg), 0) AS supply_kg
            FROM farmer_declarations fd
            JOIN ghana_districts gd ON gd.id = fd.district_id
            WHERE fd.crop   = :crop
              AND fd.status = 'active'
              AND fd.harvest_date BETWEEN :hfrom AND :hto
            GROUP BY gd.region_name
            ORDER BY supply_kg DESC
        """), date_range).fetchall()

    @staticmethod
    def get_surge_weeks(db: Session, date_range: dict):
        return db.execute(text("""
            SELECT DATE_TRUNC('week', harvest_date) AS week_start,
                   COUNT(*) AS listings
            FROM farmer_declarations
            WHERE crop   = :crop
              AND status = 'active'
              AND harvest_date BETWEEN :hfrom AND :hto
            GROUP BY week_start
            HAVING COUNT(*) >= 5
            ORDER BY week_start ASC
        """), date_range).fetchall()
