from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


class ByproductRepo:

    @staticmethod
    def search_with_distance(
        db: Session,
        byproduct_type: str,
        buyer_district_id: int,
        today: date,
        window_to: date,
    ):
        return db.execute(text("""
            SELECT bd.id          AS byproduct_id,
                   bd.declaration_id,
                   bd.byproduct_type,
                   bd.estimated_quantity_kg,
                   bd.is_perishable,
                   bd.available_date,
                   fd.farmer_id,
                   fd.crop,
                   fd.district_id,
                   f.full_name    AS farmer_name,
                   gd.district_name,
                   gd.region_name,
                   COALESCE(dd.road_distance_km, 0) AS road_distance_km
            FROM byproduct_declarations bd
            JOIN farmer_declarations fd ON fd.id = bd.declaration_id
            JOIN farmers f              ON f.id  = fd.farmer_id
            JOIN ghana_districts gd     ON gd.id = fd.district_id
            LEFT JOIN district_distances dd
                   ON dd.from_district_id = fd.district_id
                  AND dd.to_district_id   = :buyer_did
            WHERE bd.byproduct_type = :btype
              AND bd.status         = 'active'
              AND bd.available_date BETWEEN :hfrom AND :hto
        """), {
            "btype":     byproduct_type,
            "buyer_did": buyer_district_id,
            "hfrom":     today,
            "hto":       window_to,
        }).fetchall()

    @staticmethod
    def search_without_buyer(
        db: Session,
        byproduct_type: str,
        today: date,
        window_to: date,
    ):
        return db.execute(text("""
            SELECT bd.id          AS byproduct_id,
                   bd.declaration_id,
                   bd.byproduct_type,
                   bd.estimated_quantity_kg,
                   bd.is_perishable,
                   bd.available_date,
                   fd.farmer_id,
                   fd.crop,
                   fd.district_id,
                   f.full_name    AS farmer_name,
                   gd.district_name,
                   gd.region_name,
                   NULL::numeric  AS road_distance_km
            FROM byproduct_declarations bd
            JOIN farmer_declarations fd ON fd.id = bd.declaration_id
            JOIN farmers f              ON f.id  = fd.farmer_id
            JOIN ghana_districts gd     ON gd.id = fd.district_id
            WHERE bd.byproduct_type = :btype
              AND bd.status         = 'active'
              AND bd.available_date BETWEEN :hfrom AND :hto
        """), {
            "btype": byproduct_type,
            "hfrom": today,
            "hto":   window_to,
        }).fetchall()

    @staticmethod
    def get_all_byproduct_types(db: Session, today: date, window_to: date):
        return db.execute(text("""
            SELECT bd.byproduct_type,
                   COUNT(*)                                    AS total_listings,
                   COALESCE(SUM(bd.estimated_quantity_kg), 0) AS total_kg,
                   BOOL_OR(bd.is_perishable)                  AS is_perishable,
                   MIN(bd.available_date)                     AS nearest_date,
                   ARRAY_AGG(DISTINCT gd.region_name)         AS regions
            FROM byproduct_declarations bd
            JOIN farmer_declarations fd ON fd.id = bd.declaration_id
            JOIN ghana_districts gd     ON gd.id = fd.district_id
            WHERE bd.status    = 'active'
              AND fd.status    = 'active'
              AND bd.available_date BETWEEN :hfrom AND :hto
            GROUP BY bd.byproduct_type
            ORDER BY total_kg DESC
        """), {"hfrom": today, "hto": window_to}).fetchall()

    @staticmethod
    def get_farmer_byproducts(db: Session, farmer_id: int):
        return db.execute(text("""
            SELECT bd.id, bd.declaration_id, bd.byproduct_type,
                   bd.estimated_quantity_kg, bd.is_perishable,
                   bd.available_date, bd.status,
                   fd.crop, fd.harvest_date,
                   gd.district_name, gd.region_name
            FROM byproduct_declarations bd
            JOIN farmer_declarations fd ON fd.id = bd.declaration_id
            JOIN ghana_districts gd     ON gd.id = fd.district_id
            WHERE fd.farmer_id = :fid
              AND fd.status    = 'active'
            ORDER BY bd.available_date ASC, bd.byproduct_type ASC
        """), {"fid": farmer_id}).fetchall()
