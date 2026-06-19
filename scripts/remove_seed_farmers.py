"""Remove seed farmers and their declarations from the DB.

Keeps:
  - farmer_data_import (real farmers from Farmer_data.xlsx)
  - ussd / web / field_agent entries

Removes:
  - All declarations with source='seed'
  - All farmers who have no remaining declarations after the delete
"""
import sys; sys.path.insert(0, '.')
from db.connection import get_session
from sqlalchemy import text

with get_session() as db:
    # 1. Find farmer IDs that will be left with zero declarations after seed removal
    orphan_farmers = db.execute(text("""
        SELECT DISTINCT f.id, f.full_name, f.district_id
        FROM farmers f
        WHERE EXISTS (
            SELECT 1 FROM farmer_declarations fd
            WHERE fd.farmer_id = f.id AND fd.source = 'seed'
        )
        AND NOT EXISTS (
            SELECT 1 FROM farmer_declarations fd
            WHERE fd.farmer_id = f.id AND fd.source <> 'seed'
        )
    """)).fetchall()

    print(f"Farmers to delete (seed-only): {len(orphan_farmers)}")
    for r in orphan_farmers:
        print(f"  id={r[0]}  {r[1]}  district_id={r[2]}")

    # 2. Delete child rows that reference seed declarations (foreign keys)
    bp = db.execute(text("""
        DELETE FROM byproduct_declarations
        WHERE declaration_id IN (
            SELECT id FROM farmer_declarations WHERE source = 'seed'
        )
    """))
    print(f"\nDeleted {bp.rowcount} byproduct_declarations")

    # Also clear any alerts_log rows linked to seed declarations
    al = db.execute(text("""
        DELETE FROM alerts_log
        WHERE declaration_id IN (
            SELECT id FROM farmer_declarations WHERE source = 'seed'
        )
    """))
    print(f"Deleted {al.rowcount} alerts_log rows")

    # 3. Delete seed declarations
    d_result = db.execute(text(
        "DELETE FROM farmer_declarations WHERE source = 'seed'"
    ))
    print(f"\nDeleted {d_result.rowcount} seed declarations")

    # 3. Delete farmers who now have no declarations
    orphan_ids = [r[0] for r in orphan_farmers]
    if orphan_ids:
        f_result = db.execute(
            text("DELETE FROM farmers WHERE id = ANY(:ids)"),
            {"ids": orphan_ids}
        )
        print(f"Deleted {f_result.rowcount} seed farmers")
    else:
        print("No orphan farmers to delete")

    print()
    # 4. Final counts
    total_f = db.execute(text("SELECT COUNT(*) FROM farmers")).scalar()
    total_d = db.execute(text("SELECT COUNT(*) FROM farmer_declarations")).scalar()
    print(f"Remaining farmers      : {total_f}")
    print(f"Remaining declarations : {total_d}")

    rows = db.execute(text("""
        SELECT source, COUNT(*) FROM farmer_declarations GROUP BY source ORDER BY source
    """)).fetchall()
    print("\nDeclarations by source:")
    for r in rows:
        print(f"  {r[0]:<25} {r[1]}")
