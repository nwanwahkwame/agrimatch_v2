from sqlalchemy import text
from sqlalchemy.orm import Session


class DelayClassifierRepo:

    @staticmethod
    def get_climate_indicators(db: Session, district_id: int):
        """Return the 3 most recent climate indicator rows for a district."""
        return db.execute(
            text("""
                SELECT district_id, indicator_date, spi_30day, et0_mm
                FROM climate_indicators
                WHERE district_id = :did
                ORDER BY indicator_date DESC
                LIMIT 3
            """),
            {"did": district_id},
        ).fetchall()

    @staticmethod
    def get_active_declarations(db: Session):
        """Return all active farmer declarations for bulk delay update."""
        return db.execute(
            text("""
                SELECT id, district_id, harvest_date,
                       csi_flag, adjusted_harvest_date
                FROM farmer_declarations
                WHERE status = 'active'
            """)
        ).fetchall()

    @staticmethod
    def update_declaration_delay(
        db: Session,
        declaration_id: int,
        flag: str,
        adj_date,
    ) -> None:
        db.execute(
            text("""
                UPDATE farmer_declarations
                SET csi_flag              = :flag,
                    adjusted_harvest_date = :adj_date,
                    updated_at            = now()
                WHERE id = :did
            """),
            {"flag": flag, "adj_date": adj_date, "did": declaration_id},
        )
