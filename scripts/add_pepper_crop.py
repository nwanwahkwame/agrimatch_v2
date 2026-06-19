"""Add pepper to crop_reference and create declarations for skipped farmers."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_session
from sqlalchemy import text

with get_session() as db:
    existing = db.execute(
        text("SELECT id FROM crop_reference WHERE internal_name = 'pepper'")
    ).fetchone()
    if existing:
        print(f"Pepper already exists with id={existing[0]}")
    else:
        row = db.execute(text("""
            INSERT INTO crop_reference
                (internal_name, hdx_names, mofa_names, default_unit, is_byproduct_source, byproduct_types)
            VALUES
                ('pepper', '{}'::text[], '{PEPPER}'::text[], 'kg', false, '[]'::jsonb)
            RETURNING id
        """)).fetchone()
        db.commit()
        print(f"Pepper added to crop_reference with id={row[0]}")
