"""
Fix district matching for markets that were missed or wrongly matched
by populate_markets.py.

Applies 7 explicit corrections by ILIKE pattern, then attempts
word-based region-filtered matching for remaining NULLs.

Usage (from project root):
    python setup/fix_market_districts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_session
from sqlalchemy import text

# Market name -> ILIKE pattern for the correct target district
EXPLICIT = [
    ("Bunkprugu",        "%Bunkpurugu%"),
    ("Sekondi-Takoradi", "%Sekondi%"),
    ("Kete Krachi",      "%Krachi East%"),
    ("Kajeji",           "%Kadjebi%"),
    ("Navrongo",         "%Kassena%Nankana%West%"),
    ("Wa",               "%Wa Municipal%"),
    ("Ho",               "%Ho Municipal%"),
]


def fetch_district(s, pattern):
    return s.execute(text("""
        SELECT id, district_name, region_name, centroid_lat, centroid_lon
        FROM ghana_districts
        WHERE district_name ILIKE :p
        ORDER BY LENGTH(district_name)
        LIMIT 1
    """), {"p": pattern}).first()


def set_district(s, market_id, district):
    s.execute(text("""
        UPDATE ghana_markets
        SET district_id  = :did,
            centroid_lat = :lat,
            centroid_lon = :lon
        WHERE id = :mid
    """), {
        "did": district.id,
        "lat": district.centroid_lat,
        "lon": district.centroid_lon,
        "mid": market_id,
    })


def word_candidates(s, market_name, region, with_region):
    words = [w for w in market_name.replace("-", " ").split() if len(w) > 2]
    seen = set()
    out = []
    for word in words:
        if with_region:
            rows = s.execute(text("""
                SELECT id, district_name, region_name, centroid_lat, centroid_lon
                FROM ghana_districts
                WHERE district_name ILIKE :pat
                  AND region_name   ILIKE :reg
            """), {"pat": f"%{word}%", "reg": f"%{region}%"}).all()
        else:
            rows = s.execute(text("""
                SELECT id, district_name, region_name, centroid_lat, centroid_lon
                FROM ghana_districts
                WHERE district_name ILIKE :pat
            """), {"pat": f"%{word}%"}).all()
        for r in rows:
            if r.id not in seen:
                seen.add(r.id)
                out.append(r)
    return out


with get_session() as s:

    # ── 1. Explicit corrections ───────────────────────────────────────────────

    print("Applying explicit corrections ...")
    print()

    for market_name, pattern in EXPLICIT:
        market = s.execute(text(
            "SELECT id FROM ghana_markets WHERE market_name = :n"
        ), {"n": market_name}).first()

        district = fetch_district(s, pattern)

        if not market:
            print(f"  SKIP  {market_name:<28}  (market not in ghana_markets)")
            continue
        if not district:
            print(f"  SKIP  {market_name:<28}  (no district matches '{pattern}')")
            continue

        set_district(s, market.id, district)
        print(f"  OK    {market_name:<28} -> {district.district_name}")

    # ── 2. Word-based matching for remaining NULLs ────────────────────────────

    print()
    print("Word-based matching for remaining unmatched markets ...")
    print()

    still_null = s.execute(text("""
        SELECT id, market_name, region
        FROM ghana_markets
        WHERE district_id IS NULL
        ORDER BY market_name
    """)).all()

    auto_fixed = []
    needs_review = []

    for m in still_null:
        region = (m.region or "").strip()

        # Try within same region first; fall back to all regions
        candidates = word_candidates(s, m.market_name, region, with_region=True)
        if not candidates:
            candidates = word_candidates(s, m.market_name, region, with_region=False)

        if len(candidates) == 1:
            d = candidates[0]
            set_district(s, m.id, d)
            auto_fixed.append((m.market_name, d.district_name))
            print(f"  AUTO  {m.market_name:<28} -> {d.district_name}  ({d.region_name})")
        else:
            cand_names = [c.district_name for c in candidates[:5]]
            needs_review.append((m, cand_names))

    # ── 3. Needs-review output ────────────────────────────────────────────────

    if needs_review:
        print()
        print(f"NEEDS MANUAL REVIEW ({len(needs_review)}):")
        print()
        for m, cand_names in needs_review:
            cands = ", ".join(cand_names) if cand_names else "none found"
            print(f"  NEEDS MANUAL REVIEW: {m.market_name} in {m.region} -- candidates: {cands}")

        print()
        print("SQL UPDATE statements to fix manually:")
        print()
        for m, cand_names in needs_review:
            print(f"  -- {m.market_name} ({m.region})")
            for c in cand_names:
                print(f"  --   candidate: {c}")
            print(f"  UPDATE ghana_markets")
            print(f"  SET district_id  = (SELECT id   FROM ghana_districts WHERE district_name = '<REPLACE>'),")
            print(f"      centroid_lat = (SELECT centroid_lat FROM ghana_districts WHERE district_name = '<REPLACE>'),")
            print(f"      centroid_lon = (SELECT centroid_lon FROM ghana_districts WHERE district_name = '<REPLACE>')")
            print(f"  WHERE market_name = '{m.market_name}';")
            print()

    # ── 4. Final summary ──────────────────────────────────────────────────────

    print()
    print("=" * 85)
    print("FINAL MARKET-DISTRICT SUMMARY (all 44 markets)")
    print("=" * 85)
    print()

    rows = s.execute(text("""
        SELECT m.market_name,
               m.region,
               d.district_name,
               COALESCE(m.centroid_lat, d.centroid_lat) AS lat,
               COALESCE(m.centroid_lon, d.centroid_lon) AS lon
        FROM ghana_markets m
        LEFT JOIN ghana_districts d ON m.district_id = d.id
        ORDER BY m.region, m.market_name
    """)).all()

    print(f"  {'Market':<28} {'Region':<22} {'District':<32} {'Lat':>8} {'Lon':>9}")
    print("  " + "-" * 103)

    final_unmatched = []
    for r in rows:
        dist = r.district_name if r.district_name else "*** UNMATCHED ***"
        lat  = f"{float(r.lat):.4f}" if r.lat is not None else "-"
        lon  = f"{float(r.lon):.4f}" if r.lon is not None else "-"
        print(f"  {r.market_name:<28} {r.region:<22} {dist:<32} {lat:>8} {lon:>9}")
        if not r.district_name:
            final_unmatched.append(r.market_name)

    print()
    print("=" * 85)
    print(f"  Total markets   : {len(rows)}")
    print(f"  Matched         : {len(rows) - len(final_unmatched)}")
    print(f"  Still unmatched : {len(final_unmatched)}")
    print("=" * 85)

    if final_unmatched:
        print()
        print("Run these SQL statements to complete the fix:")
        print()
        for name in final_unmatched:
            print(f"  -- {name}")
            print(f"  UPDATE ghana_markets")
            print(f"  SET district_id  = (SELECT id FROM ghana_districts WHERE district_name = '<DISTRICT_NAME>'),")
            print(f"      centroid_lat = (SELECT centroid_lat FROM ghana_districts WHERE district_name = '<DISTRICT_NAME>'),")
            print(f"      centroid_lon = (SELECT centroid_lon FROM ghana_districts WHERE district_name = '<DISTRICT_NAME>')")
            print(f"  WHERE market_name = '{name}';")
            print()
