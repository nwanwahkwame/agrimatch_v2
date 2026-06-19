import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SAFE_FILTERS: frozenset = frozenset({
    "fd.status = 'active'",
    "d.region_name = :region",
    "fd.crop = :crop",
})


class ListingsRepo:

    @staticmethod
    def get_farmer_profile(db: Session, farmer_id: int):
        """Return (farmer_row, active_listings, completed_sales_count) in one round-trip."""
        farmer = db.execute(text("""
            SELECT f.id, f.full_name, gd.district_name, gd.region_name, f.created_at,
                   COUNT(fd.id) FILTER (WHERE fd.status = 'active') AS active_count,
                   COUNT(r.id) FILTER (WHERE r.status = 'confirmed')  AS sales_count
            FROM farmers f
            LEFT JOIN ghana_districts gd       ON gd.id = f.district_id
            LEFT JOIN farmer_declarations fd   ON fd.farmer_id = f.id
            LEFT JOIN reservations r           ON r.declaration_id = fd.id
            WHERE f.id = :fid
            GROUP BY f.id, f.full_name, gd.district_name, gd.region_name, f.created_at
        """), {"fid": farmer_id}).fetchone()
        if farmer is None:
            return None, [], 0
        listings = db.execute(text("""
            SELECT id, crop, quantity_kg, harvest_date,
                   price_forecast_ghs, csi_flag
            FROM farmer_declarations
            WHERE farmer_id = :fid AND status = 'active'
            ORDER BY harvest_date ASC
        """), {"fid": farmer_id}).fetchall()
        return farmer, listings, int(farmer.sales_count or 0)

    @staticmethod
    def get_all_active(db: Session, region: str = "", crop: str = "", limit: int = 100):
        filters = ["fd.status = 'active'"]
        params: dict = {"lim": limit}
        if region:
            filters.append("d.region_name = :region")
            params["region"] = region
        if crop:
            filters.append("fd.crop = :crop")
            params["crop"] = crop
        unexpected = [f for f in filters if f not in _SAFE_FILTERS]
        if unexpected:
            raise ValueError(f"Unexpected filter clause(s): {unexpected}")
        where = " AND ".join(filters)
        return db.execute(text(f"""
            SELECT
                fd.id               AS declaration_id,
                f.full_name         AS farmer_name,
                fd.crop,
                fd.quantity_kg,
                fd.harvest_date,
                fd.price_forecast_ghs,
                fd.csi_flag,
                fd.adjusted_harvest_date,
                fd.created_at,
                fd.source,
                d.district_name     AS district,
                d.region_name       AS region,
                (fd.created_at >= NOW() - INTERVAL '7 days') AS is_new
            FROM farmer_declarations fd
            JOIN farmers f         ON f.id  = fd.farmer_id
            JOIN ghana_districts d ON d.id  = f.district_id
            WHERE {where}
            ORDER BY fd.harvest_date ASC NULLS LAST, fd.created_at DESC
            LIMIT :lim
        """), params).fetchall()

    @staticmethod
    def get_fresh(db: Session, limit: int = 40):
        return db.execute(text("""
            SELECT
                fd.id               AS declaration_id,
                f.full_name         AS farmer_name,
                fd.crop,
                fd.quantity_kg,
                fd.harvest_date,
                fd.price_forecast_ghs,
                fd.csi_flag,
                fd.adjusted_harvest_date,
                fd.created_at,
                d.district_name     AS district,
                d.region_name       AS region,
                (fd.created_at >= NOW() - INTERVAL '7 days') AS is_new
            FROM farmer_declarations fd
            JOIN farmers f         ON f.id = fd.farmer_id
            JOIN ghana_districts d ON d.id = f.district_id
            WHERE fd.status = 'active'
              AND fd.harvest_date >= CURRENT_DATE
            ORDER BY fd.harvest_date ASC, fd.created_at DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()

    @staticmethod
    def get_by_id(db: Session, declaration_id: int):
        return db.execute(text("""
            SELECT
                fd.id,
                fd.farmer_id,
                fd.crop,
                fd.quantity_kg,
                fd.harvest_date,
                fd.adjusted_harvest_date,
                fd.status,
                fd.price_forecast_ghs,
                fd.csi_flag,
                fd.source,
                f.full_name      AS farmer_name,
                d.id             AS district_id,
                d.district_name
            FROM farmer_declarations fd
            JOIN farmers f         ON f.id = fd.farmer_id
            JOIN ghana_districts d ON d.id = f.district_id
            WHERE fd.id = :did
        """), {"did": declaration_id}).fetchone()

    @staticmethod
    def get_best_prices(db: Session, limit: int = 20):
        return db.execute(text("""
            SELECT
                fd.id            AS declaration_id,
                f.full_name      AS farmer_name,
                fd.crop,
                fd.quantity_kg,
                fd.harvest_date,
                fd.price_forecast_ghs,
                fd.csi_flag,
                fd.adjusted_harvest_date,
                d.district_name  AS district,
                d.region_name    AS region
            FROM farmer_declarations fd
            JOIN farmers f         ON f.id = fd.farmer_id
            JOIN ghana_districts d ON d.id = f.district_id
            WHERE fd.status = 'active'
              AND fd.price_forecast_ghs IS NOT NULL
            ORDER BY fd.price_forecast_ghs DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()
