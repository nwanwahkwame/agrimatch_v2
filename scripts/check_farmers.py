import sys; sys.path.insert(0, '.')
from db.connection import get_session
from sqlalchemy import text

with get_session() as db:
    cols = db.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='ghana_districts' ORDER BY ordinal_position"
    )).fetchall()
    print('ghana_districts columns:', [c[0] for c in cols])

    print()
    rows = db.execute(text("""
        SELECT fd.source, f.district_id, COUNT(DISTINCT f.id) as farmers, COUNT(fd.id) as decls
        FROM farmer_declarations fd
        JOIN farmers f ON f.id = fd.farmer_id
        GROUP BY fd.source, f.district_id
        ORDER BY fd.source, f.district_id
    """)).fetchall()
    print('source                    | district_id | farmers | declarations')
    for r in rows:
        print(f'  {r[0]:<25} dist={r[1]}  farmers={r[2]}  decls={r[3]}')

    print()
    orphans = db.execute(text("""
        SELECT COUNT(*) FROM farmers f
        WHERE NOT EXISTS (SELECT 1 FROM farmer_declarations fd WHERE fd.farmer_id = f.id)
    """)).scalar()
    print(f'Farmers with no declarations: {orphans}')

    total_f = db.execute(text("SELECT COUNT(*) FROM farmers")).scalar()
    total_d = db.execute(text("SELECT COUNT(*) FROM farmer_declarations")).scalar()
    print(f'Total farmers: {total_f}  Total declarations: {total_d}')
