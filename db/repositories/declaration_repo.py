from sqlalchemy import text
from sqlalchemy.orm import Session


class DeclarationRepo:

    @staticmethod
    def get_price(db: Session, declaration_id: int):
        """Read-only fetch of price and quantity -- used to estimate charge amount before locking."""
        return db.execute(text("""
            SELECT price_forecast_ghs, quantity_kg
            FROM farmer_declarations
            WHERE id = :did AND status = 'active'
        """), {"did": declaration_id}).fetchone()

    @staticmethod
    def lock_active(db: Session, declaration_id: int):
        """SELECT FOR UPDATE on an active declaration — blocks concurrent reservations."""
        return db.execute(text("""
            SELECT id, crop, price_forecast_ghs, quantity_kg
            FROM farmer_declarations
            WHERE id = :did AND status = 'active'
            FOR UPDATE
        """), {"did": declaration_id}).fetchone()

    @staticmethod
    def reserved_bags(db: Session, declaration_id: int) -> int:
        """Sum of non-cancelled reservation bags for a declaration."""
        result = db.execute(text("""
            SELECT COALESCE(SUM(quantity_bags), 0)
            FROM reservations
            WHERE declaration_id = :did AND status != 'cancelled'
        """), {"did": declaration_id}).scalar()
        return int(result or 0)

    @staticmethod
    def get_active_by_farmer(db: Session, farmer_id: int):
        return db.execute(text("""
            SELECT id, crop, quantity_kg, harvest_date,
                   price_forecast_ghs, csi_flag, source
            FROM farmer_declarations
            WHERE farmer_id = :fid AND status = 'active'
            ORDER BY harvest_date ASC
        """), {"fid": farmer_id}).fetchall()

    @staticmethod
    def get_all_active(db: Session):
        return db.execute(text("""
            SELECT id, district_id, harvest_date,
                   csi_flag, adjusted_harvest_date
            FROM farmer_declarations
            WHERE status = 'active'
        """)).fetchall()
