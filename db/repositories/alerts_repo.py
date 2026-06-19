from sqlalchemy import text
from sqlalchemy.orm import Session


class AlertsRepo:

    @staticmethod
    def get_for_farmer(db: Session, farmer_id: int, limit: int = 50) -> list:
        rows = db.execute(text("""
            SELECT id, declaration_id, phone_number, alert_type,
                   message, status, sent_at, error_detail
            FROM alerts_log
            WHERE farmer_id = :fid
            ORDER BY sent_at DESC
            LIMIT :lim
        """), {"fid": farmer_id, "lim": limit}).fetchall()

        return [
            {
                "id":             int(r.id),
                "declaration_id": int(r.declaration_id) if r.declaration_id else None,
                "phone_number":   str(r.phone_number),
                "alert_type":     str(r.alert_type),
                "message":        str(r.message),
                "status":         str(r.status),
                "sent_at":        r.sent_at.isoformat() if r.sent_at else None,
                "error_detail":   str(r.error_detail) if r.error_detail else None,
            }
            for r in rows
        ]
