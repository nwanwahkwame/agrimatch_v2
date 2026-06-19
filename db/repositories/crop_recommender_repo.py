from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


class CropRecommenderRepo:

    @staticmethod
    def get_climate_indicators_latest(db: Session, district_id: int):
        return db.execute(
            text("""
                SELECT csi_maize, csi_tomato, csi_onion,
                       csi_cassava, csi_rice, csi_plantain
                FROM climate_indicators
                WHERE district_id = :did
                ORDER BY indicator_date DESC
                LIMIT 1
            """),
            {"did": district_id},
        ).fetchone()

    @staticmethod
    def get_regional_supply(
        db: Session,
        district_id: int,
        crop: str,
        harvest_from: date,
        harvest_to: date,
    ):
        return db.execute(
            text("""
                SELECT COALESCE(SUM(fd.quantity_kg), 0) AS total_kg
                FROM farmer_declarations fd
                JOIN ghana_districts fd_dist ON fd_dist.id = fd.district_id
                WHERE fd.status = 'active'
                  AND fd.crop = :crop
                  AND fd_dist.region_name = (
                      SELECT region_name FROM ghana_districts WHERE id = :did
                  )
                  AND fd.harvest_date BETWEEN :hfrom AND :hto
            """),
            {"did": district_id, "crop": crop, "hfrom": harvest_from, "hto": harvest_to},
        ).fetchone()

    @staticmethod
    def get_district_coords(db: Session, district_id: int):
        return db.execute(
            text("""
                SELECT centroid_lat, centroid_lon
                FROM ghana_districts
                WHERE id = :did
                LIMIT 1
            """),
            {"did": district_id},
        ).fetchone()

    @staticmethod
    def get_markets_with_coords(db: Session):
        return db.execute(
            text("""
                SELECT gm.canonical_name, gd.centroid_lat, gd.centroid_lon
                FROM ghana_markets gm
                JOIN ghana_districts gd ON gd.id = gm.district_id
                WHERE gd.centroid_lat IS NOT NULL
                  AND gd.centroid_lon IS NOT NULL
            """)
        ).fetchall()

    @staticmethod
    def get_bulk_data(
        db: Session,
        district_id: int,
        crops: list,
        harvest_from: date,
        harvest_to: date,
    ) -> tuple:
        """Fetch district coords, latest climate row, all markets, and regional
        supply for all crops in a single session to avoid N round-trips."""
        dist_row = db.execute(
            text("""
                SELECT centroid_lat, centroid_lon, region_name
                FROM ghana_districts WHERE id = :did LIMIT 1
            """),
            {"did": district_id},
        ).fetchone()

        climate_row = db.execute(
            text("""
                SELECT csi_maize, csi_tomato, csi_onion,
                       csi_cassava, csi_rice, csi_plantain
                FROM climate_indicators
                WHERE district_id = :did
                ORDER BY indicator_date DESC LIMIT 1
            """),
            {"did": district_id},
        ).fetchone()

        markets = db.execute(
            text("""
                SELECT gm.canonical_name, gd.centroid_lat, gd.centroid_lon
                FROM ghana_markets gm
                JOIN ghana_districts gd ON gd.id = gm.district_id
                WHERE gd.centroid_lat IS NOT NULL
                  AND gd.centroid_lon IS NOT NULL
            """)
        ).fetchall()

        region = dist_row.region_name if dist_row else None
        supply_rows = []
        if region:
            supply_rows = db.execute(
                text("""
                    SELECT fd.crop, COALESCE(SUM(fd.quantity_kg), 0) AS total_kg
                    FROM farmer_declarations fd
                    JOIN ghana_districts fd_dist ON fd_dist.id = fd.district_id
                    WHERE fd.status = 'active'
                      AND fd.crop = ANY(:crops)
                      AND fd_dist.region_name = :region
                      AND fd.harvest_date BETWEEN :hfrom AND :hto
                    GROUP BY fd.crop
                """),
                {
                    "crops":  crops,
                    "region": region,
                    "hfrom":  harvest_from,
                    "hto":    harvest_to,
                },
            ).fetchall()

        return dist_row, climate_row, markets, supply_rows

    @staticmethod
    def get_farmer_info(db: Session, farmer_id: int):
        return db.execute(
            text("""
                SELECT f.full_name, f.district_id, gd.district_name
                FROM farmers f
                LEFT JOIN ghana_districts gd ON gd.id = f.district_id
                WHERE f.id = :fid
                LIMIT 1
            """),
            {"fid": farmer_id},
        ).fetchone()
