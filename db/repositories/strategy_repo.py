from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session


class StrategyRepo:

    @staticmethod
    def get_district_centroid(db: Session, district_id: int):
        return db.execute(text("""
            SELECT centroid_lat, centroid_lon
            FROM ghana_districts WHERE id = :did LIMIT 1
        """), {"did": district_id}).fetchone()

    @staticmethod
    def get_all_markets_with_coords(db: Session) -> list:
        return db.execute(text("""
            SELECT gm.canonical_name, gm.district_id,
                   gd.centroid_lat, gd.centroid_lon
            FROM ghana_markets gm
            JOIN ghana_districts gd ON gd.id = gm.district_id
            WHERE gm.district_id IS NOT NULL
              AND gd.centroid_lat IS NOT NULL
        """)).fetchall()

    @staticmethod
    def get_active_declaration(db: Session, declaration_id: int):
        return db.execute(text("""
            SELECT fd.id, fd.farmer_id, fd.crop,
                   fd.quantity_kg, fd.district_id,
                   fd.harvest_date, fd.adjusted_harvest_date,
                   fd.price_forecast_ghs, fd.csi_flag,
                   f.full_name AS farmer_name
            FROM farmer_declarations fd
            JOIN farmers f ON f.id = fd.farmer_id
            WHERE fd.id = :did AND fd.status = 'active'
        """), {"did": declaration_id}).fetchone()

    @staticmethod
    def get_nearby_supplier_listings(db: Session, crop: str, buyer_district_id: int) -> list:
        from datetime import timedelta
        return db.execute(text("""
            SELECT fd.id, fd.district_id, fd.quantity_kg,
                   fd.harvest_date, fd.price_forecast_ghs,
                   gd.district_name,
                   dd.road_distance_km
            FROM farmer_declarations fd
            JOIN ghana_districts gd ON gd.id = fd.district_id
            LEFT JOIN district_distances dd
                   ON dd.from_district_id = fd.district_id
                  AND dd.to_district_id   = :buyer_did
            WHERE fd.crop   = :crop
              AND fd.status = 'active'
              AND fd.harvest_date BETWEEN :hfrom AND :hto
            ORDER BY dd.road_distance_km ASC NULLS LAST
            LIMIT 5
        """), {
            "buyer_did": buyer_district_id,
            "crop":      crop,
            "hfrom":     date.today(),
            "hto":       date.today() + timedelta(days=60),
        }).fetchall()

    @staticmethod
    def get_logistics_declaration(db: Session, declaration_id: int):
        return db.execute(text("""
            SELECT fd.id, fd.farmer_id, fd.district_id,
                   fd.harvest_date, fd.quantity_kg, fd.crop,
                   f.full_name AS farmer_name
            FROM farmer_declarations fd
            JOIN farmers f ON f.id = fd.farmer_id
            WHERE fd.id = :did AND fd.status = 'active'
        """), {"did": declaration_id}).fetchone()

    @staticmethod
    def get_nearby_declarations(
        db: Session,
        declaration_id: int,
        home_district_id: int,
        window_from: date,
        window_to: date,
    ) -> list:
        return db.execute(text("""
            SELECT fd.id, fd.farmer_id, fd.district_id,
                   fd.quantity_kg, fd.harvest_date,
                   f.full_name AS farmer_name,
                   gd.district_name,
                   COALESCE(dd.road_distance_km, 0) AS road_distance_km
            FROM farmer_declarations fd
            JOIN farmers f ON f.id = fd.farmer_id
            JOIN ghana_districts gd ON gd.id = fd.district_id
            LEFT JOIN district_distances dd
                   ON dd.from_district_id = fd.district_id
                  AND dd.to_district_id   = :home_did
            WHERE fd.status = 'active'
              AND fd.id    != :did
              AND fd.harvest_date BETWEEN :wfrom AND :wto
              AND (fd.district_id = :home_did
                   OR dd.road_distance_km <= 50)
            ORDER BY road_distance_km ASC
            LIMIT 10
        """), {
            "home_did": home_district_id,
            "did":      declaration_id,
            "wfrom":    window_from,
            "wto":      window_to,
        }).fetchall()

    @staticmethod
    def get_active_declaration_ids(db: Session, farmer_id: int) -> list:
        return db.execute(text("""
            SELECT id FROM farmer_declarations
            WHERE farmer_id = :fid AND status = 'active'
            ORDER BY harvest_date ASC
        """), {"fid": farmer_id}).fetchall()
