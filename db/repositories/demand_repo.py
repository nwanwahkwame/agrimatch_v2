from sqlalchemy import text
from sqlalchemy.orm import Session

_SAFE_FILTERS: frozenset = frozenset({
    "status = 'open'",
    "crop = :crop",
    "region = :region",
})


class DemandRepo:

    @staticmethod
    def create(
        db: Session,
        crop: str,
        quantity_kg: float,
        region: str,
        target_date,
        buyer_name: str,
        buyer_phone: str,
        notes: str,
    ):
        return db.execute(text("""
            INSERT INTO buyer_requests
                (crop, quantity_kg, region, target_date, buyer_name, buyer_phone, notes)
            VALUES (:crop, :qty, :region, :tdate, :name, :phone, :notes)
            RETURNING id, created_at
        """), {
            "crop":   crop,
            "qty":    quantity_kg,
            "region": region or None,
            "tdate":  target_date or None,
            "name":   buyer_name,
            "phone":  buyer_phone,
            "notes":  notes or None,
        }).fetchone()

    @staticmethod
    def list_open(db: Session, crop: str = "", region: str = "", limit: int = 50):
        filters = ["status = 'open'"]
        params: dict = {"lim": limit}
        if crop:
            filters.append("crop = :crop")
            params["crop"] = crop
        if region:
            filters.append("region = :region")
            params["region"] = region
        assert all(f in _SAFE_FILTERS for f in filters), f"Unexpected filter: {filters}"
        where = " AND ".join(filters)
        return db.execute(text(f"""
            SELECT id, crop, quantity_kg, region, target_date,
                   buyer_name, notes, status, created_at
            FROM buyer_requests
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :lim
        """), params).fetchall()
