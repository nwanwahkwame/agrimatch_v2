from db.connection import get_session
from sqlalchemy import text

with get_session() as s:

    print("=== UNIT FAILURES: which crop goes with each unrecognised unit ===")
    rows = s.execute(text("""
        SELECT
            rejection_reason,
            raw_payload->>'commodity' AS commodity,
            COUNT(*)                  AS cnt
        FROM price_quarantine
        WHERE rejection_reason LIKE 'unmapped_unit:%'
        GROUP BY rejection_reason, raw_payload->>'commodity'
        ORDER BY rejection_reason, cnt DESC
    """)).all()
    for r in rows:
        print(f"  {r.rejection_reason:<30}  {r.commodity:<35}  {r.cnt}")

    print()
    print("=== CROP FAILURES: unit used for each unrecognised crop ===")
    rows2 = s.execute(text("""
        SELECT
            rejection_reason,
            raw_payload->>'unit' AS unit,
            COUNT(*)             AS cnt
        FROM price_quarantine
        WHERE rejection_reason LIKE 'unmapped_crop:%'
        GROUP BY rejection_reason, raw_payload->>'unit'
        ORDER BY rejection_reason, cnt DESC
    """)).all()
    for r in rows2:
        print(f"  {r.rejection_reason:<45}  unit={r.unit:<15}  {r.cnt}")
