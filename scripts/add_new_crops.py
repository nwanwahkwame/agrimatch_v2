"""Add soybean, millet and garden_egg to crop_reference."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_session
from sqlalchemy import text

NEW_CROPS = [
    {
        "internal_name": "soybean",
        "mofa_names":    "{soybean,SOYA,SOYA BEANS,SOYABEAN,SOYABEANS}",
        "default_unit":  "kg",
        "is_byproduct":  False,
    },
    {
        "internal_name": "millet",
        "mofa_names":    "{millet,MILLET}",
        "default_unit":  "kg",
        "is_byproduct":  False,
    },
    {
        "internal_name": "garden_egg",
        "mofa_names":    "{garden_egg,GARDEN EGG,GARDEN EGGS,GARDEN EGG (BRINJAL)}",
        "default_unit":  "kg",
        "is_byproduct":  False,
    },
]

with get_session() as db:
    for crop in NEW_CROPS:
        existing = db.execute(
            text("SELECT id FROM crop_reference WHERE internal_name = :n"),
            {"n": crop["internal_name"]}
        ).fetchone()
        if existing:
            print(f"  [skip] {crop['internal_name']} already exists (id={existing[0]})")
            continue
        mofa_literal = crop["mofa_names"]
        row = db.execute(text(f"""
            INSERT INTO crop_reference
                (internal_name, hdx_names, mofa_names, default_unit, is_byproduct_source, byproduct_types)
            VALUES
                (:n, '{{}}'::text[], '{mofa_literal}'::text[], :unit, :bp, '[]'::jsonb)
            RETURNING id
        """), {
            "n":   crop["internal_name"],
            "unit": crop["default_unit"],
            "bp":   crop["is_byproduct"],
        }).fetchone()
        db.commit()
        print(f"  [+] {crop['internal_name']} added (id={row[0]})")

print("\nFinal crop list:")
with get_session() as db:
    rows = db.execute(text("SELECT id, internal_name FROM crop_reference ORDER BY internal_name")).fetchall()
    for r in rows:
        print(f"  {r.id:3d}  {r.internal_name}")
