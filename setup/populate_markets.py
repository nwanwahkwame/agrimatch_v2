"""
Populate ghana_markets from distinct clean_prices markets, then match each
market to its district in ghana_districts.

Usage (from project root):
    python setup/populate_markets.py
"""

import sys
from difflib import get_close_matches
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_engine, get_session
from db.models import GhanaMarket
from sqlalchemy import text

MAJOR_HUBS = {
    "accra", "kumasi", "tamale", "techiman", "bolgatanga",
    "cape coast", "koforidua", "sunyani", "ho", "wa",
    "takoradi", "tema",
}

# ── 0. Schema prep ────────────────────────────────────────────────────────────

print("Checking schema ...")
with get_session() as s:
    # ghana_districts needs a surrogate id for district_id FK
    s.execute(text("""
        ALTER TABLE ghana_districts
        ADD COLUMN IF NOT EXISTS id BIGSERIAL
    """))
    # Make it the primary key only if no PK exists yet
    has_pk = s.execute(text("""
        SELECT COUNT(*) FROM information_schema.table_constraints
        WHERE table_name = 'ghana_districts'
        AND constraint_type = 'PRIMARY KEY'
    """)).scalar()
    if not has_pk:
        s.execute(text(
            "ALTER TABLE ghana_districts ADD PRIMARY KEY (id)"
        ))

    # ghana_markets needs centroid columns for the matched district
    s.execute(text("""
        ALTER TABLE ghana_markets
        ADD COLUMN IF NOT EXISTS centroid_lat DOUBLE PRECISION
    """))
    s.execute(text("""
        ALTER TABLE ghana_markets
        ADD COLUMN IF NOT EXISTS centroid_lon DOUBLE PRECISION
    """))
print("  Schema ready")

# ── 1. Fetch distinct markets from clean_prices ───────────────────────────────

print("\nQuerying distinct markets from clean_prices ...")
with get_session() as s:
    rows = s.execute(text("""
        SELECT DISTINCT market, region
        FROM clean_prices
        WHERE market IS NOT NULL
        ORDER BY market
    """)).all()

markets_raw = [(r.market, r.region) for r in rows]
print(f"  Found {len(markets_raw)} distinct markets")

# ── 2. Repopulate ghana_markets ───────────────────────────────────────────────

print("\nPopulating ghana_markets ...")
with get_session() as s:
    s.execute(text("TRUNCATE ghana_markets RESTART IDENTITY CASCADE"))

    for market_name, region in markets_raw:
        is_hub = market_name.strip().lower() in MAJOR_HUBS
        m = GhanaMarket(
            market_name=market_name,
            canonical_name=market_name,
            region=region,
            is_major_hub=is_hub,
            hdx_names=[market_name],
            mofa_names=[],
        )
        s.add(m)

print(f"  Inserted {len(markets_raw)} markets")

# ── 3. District matching (ILIKE) ──────────────────────────────────────────────

print("\nMatching markets to districts ...")

with get_session() as s:
    # Load all districts for Python-side suggestions
    all_districts = s.execute(text(
        "SELECT id, district_name, variant_names FROM ghana_districts"
    )).all()

    all_district_names = [d.district_name for d in all_districts]
    district_by_name = {d.district_name: d for d in all_districts}

    # Run ILIKE match for each market in one pass
    markets_db = s.execute(text(
        "SELECT id, market_name FROM ghana_markets ORDER BY market_name"
    )).all()

    matched = []
    unmatched = []

    for m in markets_db:
        result = s.execute(text("""
            SELECT id, district_name, centroid_lat, centroid_lon
            FROM ghana_districts
            WHERE district_name ILIKE '%' || :name || '%'
               OR :name       ILIKE '%' || district_name || '%'
               OR variant_names ILIKE '%' || :name || '%'
            ORDER BY LENGTH(district_name)
            LIMIT 1
        """), {"name": m.market_name}).first()

        if result:
            s.execute(text("""
                UPDATE ghana_markets
                SET district_id   = :did,
                    centroid_lat  = :lat,
                    centroid_lon  = :lon
                WHERE id = :mid
            """), {
                "did": result.id,
                "lat": result.centroid_lat,
                "lon": result.centroid_lon,
                "mid": m.id,
            })
            matched.append((m.market_name, result.district_name))
        else:
            unmatched.append(m.market_name)

# ── 4. Results ────────────────────────────────────────────────────────────────

print()
print("=" * 65)
print(f"  Total markets inserted : {len(markets_raw)}")
print(f"  Matched to district    : {len(matched)}")
print(f"  Unmatched              : {len(unmatched)}")
print("=" * 65)

print(f"\nMatched ({len(matched)}):")
print(f"  {'Market':<28} {'Matched District'}")
print("  " + "-" * 55)
for market, district in sorted(matched):
    print(f"  {market:<28} {district}")

if unmatched:
    print(f"\nUnmatched ({len(unmatched)}) -- manual fix needed:")
    print("  " + "-" * 65)
    for name in sorted(unmatched):
        suggestions = get_close_matches(
            name.lower(),
            [d.lower() for d in all_district_names],
            n=3,
            cutoff=0.4,
        )
        # Map back to original casing
        lower_to_orig = {d.lower(): d for d in all_district_names}
        sugg_display = ", ".join(lower_to_orig[s] for s in suggestions) if suggestions else "none found"
        print(f"  UNMATCHED: {name}")
        print(f"    nearest district suggestions: {sugg_display}")
