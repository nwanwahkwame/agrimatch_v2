from sqlalchemy import text
from sqlalchemy.orm import Session


class ReservationRepo:

    @staticmethod
    def insert_reservation(
        db: Session,
        declaration_id: int,
        buyer_phone: str,
        buyer_name: str,
        quantity_bags: int,
        unit_price: float,
        total: float,
    ) -> int:
        row = db.execute(text("""
            INSERT INTO reservations
                (declaration_id, buyer_phone, buyer_name,
                 quantity_bags, unit_price_ghs, total_ghs, status)
            VALUES (:did, :phone, :name, :qty, :unit, :total, 'confirmed')
            RETURNING id
        """), {
            "did":   declaration_id,
            "phone": buyer_phone,
            "name":  buyer_name,
            "qty":   quantity_bags,
            "unit":  unit_price,
            "total": total,
        }).fetchone()
        return row[0]

    @staticmethod
    def insert_payment(
        db: Session,
        reservation_id: int,
        provider: str,
        phone: str,
        amount: float,
        reference: str,
    ) -> None:
        db.execute(text("""
            INSERT INTO momo_payments
                (reservation_id, provider, phone_number, amount_ghs, reference, status)
            VALUES (:rid, :prov, :phone, :amt, :ref, 'success')
        """), {
            "rid":   reservation_id,
            "prov":  provider,
            "phone": phone,
            "amt":   amount,
            "ref":   reference,
        })

    @staticmethod
    def get_buyer_reservations(db: Session, phone: str):
        return db.execute(text("""
            SELECT r.id, r.declaration_id, r.quantity_bags,
                   r.total_ghs, r.status, r.created_at,
                   fd.crop, d.district_name, d.region_name,
                   p.reference, p.provider
            FROM reservations r
            JOIN farmer_declarations fd ON fd.id = r.declaration_id
            JOIN farmers f             ON f.id  = fd.farmer_id
            JOIN ghana_districts d     ON d.id  = f.district_id
            LEFT JOIN momo_payments p  ON p.reservation_id = r.id
            WHERE r.buyer_phone = :phone
            ORDER BY r.created_at DESC
        """), {"phone": phone}).fetchall()
