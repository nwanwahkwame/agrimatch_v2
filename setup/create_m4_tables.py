"""
Create M4 fuel_prices table.

Usage (from project root):
    python setup/create_m4_tables.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

DDL = [
    """
    CREATE TABLE IF NOT EXISTS fuel_prices (
        id                   BIGSERIAL PRIMARY KEY,
        price_date           DATE NOT NULL,
        fuel_type            TEXT NOT NULL,
        price_ghs_per_litre  NUMERIC(8,3) NOT NULL,
        source               TEXT DEFAULT 'npa',
        scraped_at           TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT uq_fuel_price_date_type UNIQUE (price_date, fuel_type)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_fuel_prices_price_date
        ON fuel_prices (price_date)
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

    print("Creating fuel_prices table ...")
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
        cur.execute("SELECT COUNT(*) FROM fuel_prices")
        count = cur.fetchone()[0]
        print(f"  fuel_prices rows : {count:,}")

        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'fuel_prices'
            ORDER BY indexname
        """)
        print("  Indexes:")
        for (idx,) in cur.fetchall():
            print(f"    {idx}")

    conn.close()
    print()


if __name__ == "__main__":
    main()
