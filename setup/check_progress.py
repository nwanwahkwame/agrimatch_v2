from dotenv import load_dotenv
load_dotenv(".env")
from db.connection import get_session
from sqlalchemy import text
with get_session() as db:
    total = db.execute(text("SELECT COUNT(*) FROM (SELECT DISTINCT crop, market FROM clean_prices) x")).scalar()
    done  = db.execute(text("SELECT COUNT(*) FROM (SELECT DISTINCT crop, market FROM feature_store) x")).scalar()
    rows  = db.execute(text("SELECT COUNT(*) FROM feature_store")).scalar()
print(f"Total pairs in clean_prices : {total}")
print(f"Pairs completed so far      : {done}")
print(f"feature_store rows          : {rows}")
print(f"Pairs remaining             : {total - done}")
