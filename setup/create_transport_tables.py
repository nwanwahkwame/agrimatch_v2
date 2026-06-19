"""
Create transport_providers and transport_jobs tables.

Usage (from project root):
    python setup/create_transport_tables.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DDL = [
    """
    CREATE TABLE IF NOT EXISTS transport_providers (
        id               BIGSERIAL PRIMARY KEY,
        full_name        TEXT NOT NULL,
        phone_number     TEXT NOT NULL UNIQUE,
        business_name    TEXT,
        district_id      BIGINT REFERENCES ghana_districts(id),
        truck_capacity_kg NUMERIC(10,2) NOT NULL,
        truck_count      INTEGER NOT NULL DEFAULT 1,
        vehicle_type     TEXT NOT NULL,
        is_available     BOOLEAN NOT NULL DEFAULT TRUE,
        service_regions  JSONB DEFAULT '[]'::jsonb,
        base_rate_per_km NUMERIC(8,2),
        rating           NUMERIC(3,2) NOT NULL DEFAULT 5.00,
        total_jobs       INTEGER NOT NULL DEFAULT 0,
        is_active        BOOLEAN NOT NULL DEFAULT TRUE,
        registered_at    TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_transport_providers_district_id
        ON transport_providers (district_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_transport_providers_availability
        ON transport_providers (is_available, is_active)
    """,
    """
    CREATE TABLE IF NOT EXISTS transport_jobs (
        id                    BIGSERIAL PRIMARY KEY,
        provider_id           BIGINT NOT NULL REFERENCES transport_providers(id),
        status                TEXT NOT NULL DEFAULT 'pending',
        pickup_district_id    BIGINT REFERENCES ghana_districts(id),
        delivery_district_id  BIGINT REFERENCES ghana_districts(id),
        scheduled_date        DATE NOT NULL,
        total_cargo_kg        NUMERIC(10,2),
        declaration_ids       JSONB DEFAULT '[]'::jsonb,
        farmer_ids            JSONB DEFAULT '[]'::jsonb,
        estimated_distance_km NUMERIC(8,2),
        estimated_cost_ghs    NUMERIC(10,2),
        actual_cost_ghs       NUMERIC(10,2),
        created_at            TIMESTAMPTZ DEFAULT NOW(),
        updated_at            TIMESTAMPTZ DEFAULT NOW()
    )
    """,
]


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print()
    print("Connecting to Railway PostgreSQL ...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print("Creating transport tables ...")
    with conn.cursor() as cur:
        for stmt in DDL:
            cur.execute(stmt)
    conn.commit()
    print("  Done.")

    print()
    print("=" * 50)
    print("VERIFICATION")
    print("=" * 50)
    with conn.cursor() as cur:
        print(f"  {'Table':<30} {'Rows':>8}")
        print("  " + "-" * 40)
        for table in ("transport_providers", "transport_jobs"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<30} {count:>8,}")

        print()
        print("  Indexes on transport_providers:")
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'transport_providers'
            ORDER BY indexname
        """)
        for (idx,) in cur.fetchall():
            print(f"    {idx}")

    conn.close()
    print()


if __name__ == "__main__":
    main()
