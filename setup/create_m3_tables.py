"""
Create M3 farmer-facing tables and populate crop_reference byproduct data.

Creates (if not exist):
  farmers, farmer_declarations, byproduct_declarations, ussd_sessions

Alters crop_reference:
  - adds byproduct_types JSONB column (if absent)
  - upserts 10 crop rows with is_byproduct_source and byproduct_types

Usage (from project root):
    python setup/create_m3_tables.py
"""

import sys
from pathlib import Path

import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(Path(__file__).parent.parent / ".env")


# ── Byproduct data ─────────────────────────────────────────────────────────────

def _bp(name, perishable=False):
    return {"type": name, "is_perishable": perishable}

CROP_BYPRODUCTS = [
    {
        "internal_name": "maize",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("husks"), _bp("cobs"), _bp("stalks"), _bp("bran"),
        ],
    },
    {
        "internal_name": "rice",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("husks"), _bp("bran"), _bp("straw"),
        ],
    },
    {
        "internal_name": "cassava",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("peels", perishable=True),
            _bp("bagasse"),
            _bp("leaves", perishable=True),
        ],
    },
    {
        "internal_name": "plantain",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("peels", perishable=True),
            _bp("rejected fingers", perishable=True),
            _bp("stems"),
            _bp("leaves"),
        ],
    },
    {
        "internal_name": "tomato",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("damaged fruit", perishable=True),
            _bp("seeds"),
            _bp("skins", perishable=True),
        ],
    },
    {
        "internal_name": "onion",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("outer skins"),
            _bp("rejected bulbs"),
        ],
    },
    {
        "internal_name": "sorghum",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("stalks"), _bp("husks"),
        ],
    },
    {
        "internal_name": "yam",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("peels", perishable=True),
            _bp("off-cuts", perishable=True),
        ],
    },
    {
        "internal_name": "cowpea",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("pods"), _bp("stalks"),
        ],
    },
    {
        "internal_name": "groundnut",
        "is_byproduct_source": True,
        "byproduct_types": [
            _bp("shells"), _bp("haulms"),
        ],
    },
]

# ── Main ───────────────────────────────────────────────────────────────────────

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

    # 1. Create new tables via raw DDL (ghana_districts has no ORM model so
    #    SQLAlchemy's FK sort fails; raw SQL avoids the dependency check).
    print("Creating M3 tables ...")
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS farmers (
            id              BIGSERIAL PRIMARY KEY,
            full_name       TEXT NOT NULL,
            phone_number    TEXT NOT NULL UNIQUE,
            district_id     BIGINT REFERENCES ghana_districts(id),
            registered_by   BIGINT,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS farmer_declarations (
            id                    BIGSERIAL PRIMARY KEY,
            farmer_id             BIGINT NOT NULL REFERENCES farmers(id),
            submitted_by_agent    BIGINT,
            source                TEXT NOT NULL,
            crop                  TEXT NOT NULL,
            quantity_kg           NUMERIC(10,2) NOT NULL,
            district_id           BIGINT REFERENCES ghana_districts(id),
            harvest_date          DATE NOT NULL,
            adjusted_harvest_date DATE,
            status                TEXT NOT NULL DEFAULT 'active',
            price_forecast_ghs    NUMERIC(10,2),
            csi_flag              TEXT NOT NULL DEFAULT 'normal',
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            updated_at            TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_farmer_declaration
                UNIQUE (farmer_id, crop, district_id, harvest_date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS byproduct_declarations (
            id                     BIGSERIAL PRIMARY KEY,
            declaration_id         BIGINT NOT NULL REFERENCES farmer_declarations(id),
            byproduct_type         TEXT NOT NULL,
            estimated_quantity_kg  NUMERIC(10,2),
            is_perishable          BOOLEAN NOT NULL DEFAULT FALSE,
            available_date         DATE NOT NULL,
            status                 TEXT NOT NULL DEFAULT 'active',
            created_at             TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ussd_sessions (
            id            BIGSERIAL PRIMARY KEY,
            session_id    TEXT NOT NULL UNIQUE,
            phone_number  TEXT NOT NULL,
            farmer_id     BIGINT REFERENCES farmers(id),
            menu_state    TEXT NOT NULL DEFAULT 'welcome',
            declaration   JSONB DEFAULT '{}'::jsonb,
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            last_activity TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_ussd_sessions_last_activity
            ON ussd_sessions (last_activity)
        """,
    ]
    with conn.cursor() as cur:
        for stmt in ddl_statements:
            cur.execute(stmt)
    conn.commit()
    print("  Done.")

    # 2. Add byproduct_types column to crop_reference if absent
    print("Adding byproduct_types column to crop_reference ...")
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE crop_reference
            ADD COLUMN IF NOT EXISTS byproduct_types JSONB DEFAULT '[]'::jsonb
        """)
    conn.commit()
    print("  Done.")

    # 4. Upsert crop byproduct data
    print("Populating crop_reference byproduct data ...")
    with conn.cursor() as cur:
        for crop in CROP_BYPRODUCTS:
            cur.execute("""
                INSERT INTO crop_reference (internal_name, is_byproduct_source, byproduct_types,
                                            hdx_names, mofa_names, unit_conversions)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                crop["internal_name"],
                crop["is_byproduct_source"],
                pgx.Json(crop["byproduct_types"]),
                [],
                [],
                pgx.Json({}),
            ))

            # If row existed already, update the byproduct columns
            cur.execute("""
                UPDATE crop_reference
                SET is_byproduct_source = %s,
                    byproduct_types     = %s
                WHERE internal_name = %s
                  AND (is_byproduct_source IS DISTINCT FROM %s
                    OR byproduct_types IS DISTINCT FROM %s)
            """, (
                crop["is_byproduct_source"],
                pgx.Json(crop["byproduct_types"]),
                crop["internal_name"],
                crop["is_byproduct_source"],
                pgx.Json(crop["byproduct_types"]),
            ))
    conn.commit()
    print(f"  {len(CROP_BYPRODUCTS)} crops upserted.")

    # 5. Verification query
    print()
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    tables_to_check = [
        "farmers",
        "farmer_declarations",
        "byproduct_declarations",
        "ussd_sessions",
        "crop_reference",
    ]

    with conn.cursor() as cur:
        print(f"  {'Table':<30} {'Rows':>8}")
        print("  " + "-" * 40)
        for table in tables_to_check:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<30} {count:>8,}")

        print()
        print("  crop_reference byproduct data:")
        cur.execute("""
            SELECT internal_name, is_byproduct_source,
                   jsonb_array_length(byproduct_types) AS num_byproducts
            FROM crop_reference
            ORDER BY internal_name
        """)
        rows = cur.fetchall()
        print(f"  {'Crop':<16} {'Byproduct Source':<18} {'Byproduct Types':>15}")
        print("  " + "-" * 52)
        for r in rows:
            print(f"  {r[0]:<16} {str(r[1]):<18} {r[2]:>15}")

    conn.close()
    print()


if __name__ == "__main__":
    main()
