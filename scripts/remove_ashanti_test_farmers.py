"""Remove remaining test farmers in Ashanti region (ussd/web/field_agent sources).

These are in districts 7 (Adansi Akrofuom) and 32 (Ejura-Sekyedumase) --
both Ashanti region. Only farmer_data_import entries in Greater Accra and
Upper East should remain.
"""
import sys; sys.path.insert(0, '.')
from db.connection import get_session
from sqlalchemy import text

REMOVE_SOURCES = ('ussd', 'web', 'field_agent')

with get_session() as db:
    # Show what will be removed
    rows = db.execute(text("""
        SELECT fd.source, gd.region_name, gd.district_name, f.full_name, f.id
        FROM farmer_declarations fd
        JOIN farmers f ON f.id = fd.farmer_id
        JOIN ghana_districts gd ON gd.id = f.district_id
        WHERE fd.source = ANY(:srcs)
        ORDER BY fd.source, f.id
    """), {"srcs": list(REMOVE_SOURCES)}).fetchall()

    print(f"Declarations to remove: {len(rows)}")
    for r in rows:
        print(f"  [{r[0]}] {r[1]} / {r[2]} — {r[3]} (farmer id={r[4]})")

    # Find farmers who will become orphans
    orphans = db.execute(text("""
        SELECT DISTINCT f.id, f.full_name
        FROM farmers f
        WHERE EXISTS (
            SELECT 1 FROM farmer_declarations fd
            WHERE fd.farmer_id = f.id AND fd.source = ANY(:srcs)
        )
        AND NOT EXISTS (
            SELECT 1 FROM farmer_declarations fd
            WHERE fd.farmer_id = f.id AND fd.source NOT IN ('ussd','web','field_agent')
        )
    """), {"srcs": list(REMOVE_SOURCES)}).fetchall()

    print(f"\nFarmers to delete: {len(orphans)}")
    for r in orphans:
        print(f"  id={r[0]}  {r[1]}")

    # Delete child rows first (all foreign key dependencies)
    bp = db.execute(text("""
        DELETE FROM byproduct_declarations
        WHERE declaration_id IN (
            SELECT id FROM farmer_declarations WHERE source = ANY(:srcs)
        )
    """), {"srcs": list(REMOVE_SOURCES)})
    print(f"\nDeleted {bp.rowcount} byproduct_declarations")

    al = db.execute(text("""
        DELETE FROM alerts_log
        WHERE declaration_id IN (
            SELECT id FROM farmer_declarations WHERE source = ANY(:srcs)
        )
    """), {"srcs": list(REMOVE_SOURCES)})
    print(f"Deleted {al.rowcount} alerts_log rows")

    # Delete declarations
    dr = db.execute(text(
        "DELETE FROM farmer_declarations WHERE source = ANY(:srcs)"
    ), {"srcs": list(REMOVE_SOURCES)})
    print(f"Deleted {dr.rowcount} declarations")

    # Delete all remaining rows that reference the orphan farmers directly
    orphan_ids = [r[0] for r in orphans]

    us = db.execute(text(
        "DELETE FROM ussd_sessions WHERE farmer_id = ANY(:ids)"
    ), {"ids": orphan_ids})
    print(f"Deleted {us.rowcount} ussd_sessions")

    al2 = db.execute(text(
        "DELETE FROM alerts_log WHERE farmer_id = ANY(:ids)"
    ), {"ids": orphan_ids})
    print(f"Deleted {al2.rowcount} alerts_log (farmer-level)")

    if orphan_ids:
        fr = db.execute(
            text("DELETE FROM farmers WHERE id = ANY(:ids)"),
            {"ids": orphan_ids}
        )
        print(f"Deleted {fr.rowcount} farmers")

    print()
    total_f = db.execute(text("SELECT COUNT(*) FROM farmers")).scalar()
    total_d = db.execute(text("SELECT COUNT(*) FROM farmer_declarations")).scalar()
    print(f"Remaining farmers      : {total_f}")
    print(f"Remaining declarations : {total_d}")

    rows = db.execute(text("""
        SELECT gd.region_name, gd.district_name, COUNT(fd.id) as decls
        FROM farmer_declarations fd
        JOIN farmers f ON f.id = fd.farmer_id
        JOIN ghana_districts gd ON gd.id = f.district_id
        GROUP BY gd.region_name, gd.district_name
        ORDER BY gd.region_name
    """)).fetchall()
    print("\nFinal breakdown:")
    for r in rows:
        print(f"  {r[0]:<30} {r[1]:<30} {r[2]} declarations")
