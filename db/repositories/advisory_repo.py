from sqlalchemy import text
from sqlalchemy.orm import Session


class AdvisoryRepo:

    @staticmethod
    def get_climate(db: Session, district_id: int):
        return db.execute(text("""
            SELECT spi_30day, et0_mm, flag_level, harvest_delay_days,
                   csi_maize, csi_tomato, csi_cassava, csi_onion,
                   csi_rice, csi_plantain
            FROM climate_indicators
            WHERE district_id = :did
            ORDER BY indicator_date DESC
            LIMIT 1
        """), {"did": district_id}).fetchone()

    @staticmethod
    def get_nearest_market(db: Session, target_district_id: int):
        return db.execute(text("""
            SELECT gm.canonical_name
            FROM ghana_markets gm
            JOIN ghana_districts gd ON gd.id = gm.district_id
            LEFT JOIN district_distances dd
                ON dd.from_district_id = gm.district_id
               AND dd.to_district_id   = :target_did
            ORDER BY dd.road_distance_km ASC NULLS LAST
            LIMIT 1
        """), {"target_did": target_district_id}).fetchone()

    @staticmethod
    def get_latest_price(db: Session, crop: str):
        return db.execute(text("""
            SELECT price_ghs FROM clean_prices
            WHERE crop = :crop ORDER BY price_date DESC LIMIT 1
        """), {"crop": crop}).fetchone()

    @staticmethod
    def get_district_name(db: Session, district_id: int):
        return db.execute(text("""
            SELECT district_name FROM ghana_districts WHERE id = :id
        """), {"id": district_id}).fetchone()
