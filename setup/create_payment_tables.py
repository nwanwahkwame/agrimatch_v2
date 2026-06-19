"""Create reservations and momo_payments tables."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_session
from sqlalchemy import text

TABLES = [
    text("""
    CREATE TABLE IF NOT EXISTS reservations (
        id             BIGSERIAL PRIMARY KEY,
        declaration_id BIGINT REFERENCES farmer_declarations(id) ON DELETE CASCADE,
        buyer_phone    TEXT NOT NULL,
        buyer_name     TEXT,
        quantity_bags  INT NOT NULL DEFAULT 1,
        unit_price_ghs NUMERIC(10,2),
        total_ghs      NUMERIC(10,2),
        status         TEXT NOT NULL DEFAULT 'confirmed',
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """),
    text("""
    CREATE TABLE IF NOT EXISTS momo_payments (
        id             BIGSERIAL PRIMARY KEY,
        reservation_id BIGINT REFERENCES reservations(id) ON DELETE CASCADE,
        provider       TEXT NOT NULL,
        phone_number   TEXT NOT NULL,
        amount_ghs     NUMERIC(10,2) NOT NULL,
        reference      TEXT NOT NULL UNIQUE,
        status         TEXT NOT NULL DEFAULT 'success',
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """),
    text("CREATE INDEX IF NOT EXISTS ix_reservations_declaration ON reservations(declaration_id)"),
    text("CREATE INDEX IF NOT EXISTS ix_reservations_buyer_phone ON reservations(buyer_phone)"),
]

with get_session() as db:
    for stmt in TABLES:
        db.execute(stmt)

print("reservations and momo_payments tables created.")
