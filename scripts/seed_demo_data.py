"""
Seed demo data for all AgriMatch frontend pages.
Run from project root: python scripts/seed_demo_data.py
"""
import sys
import os
import requests
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_session
from sqlalchemy import text

API = "http://localhost:8000"

# ── New farmers to insert (farmers 1-4 already exist in DB) ──────────────────
# Existing: 1=Kofi(dist 32), 2=Akosua(dist 32), 3=Ama Boateng(dist 7), 4=Ama(dist 7)
NEW_FARMERS = [
    # (full_name, phone, district_id)
    ("Abena Asante",       "0244000005", 34),   # Kumasi
    ("Kwame Boateng",      "0244000006", 31),   # Ejisu
    ("Yaw Owusu",          "0244000007", 28),   # Bekwai
    ("Kwabena Acheampong", "0244000008", 29),   # Bosome Freho
    ("Adwoa Mensah",       "0244000009", 33),   # Juaben
    ("Kojo Amponsah",      "0244000010", 30),   # Bosomtwe
]

# ── Byproducts per crop ───────────────────────────────────────────────────────
BYPRODUCTS = {
    "maize":    [("husks",          0.30, False), ("cobs",           0.20, False), ("stalks", 0.15, False)],
    "tomato":   [("damaged fruit",  0.10, True),  ("skins",          0.05, True)],
    "onion":    [("outer skins",    0.08, False),  ("rejected bulbs", 0.06, False)],
    "cassava":  [("peels",          0.12, True),   ("starch waste",   0.08, False)],
    "rice":     [("bran",           0.15, False),  ("husks",          0.20, False), ("straw", 0.25, False)],
    "plantain": [("peels",          0.10, True),   ("rejected hands", 0.05, True)],
}

# ── Declaration plan ──────────────────────────────────────────────────────────
# farmer_ids list will be built as: [id1, id2, id3, id4, id5, id6, id7, id8, id9, id10]
# Indices:  0=Kofi(32)  1=Akosua(32)  2=Ama B(7)  3=Ama(7)
#           4=Abena(34) 5=Kwame(31)   6=Yaw(28)   7=Kwabena(29)  8=Adwoa(33)  9=Kojo(30)
# (farmer_idx, crop, quantity_bags, district_id, days_until_harvest)
DECLARATIONS = [
    # ── MAIZE (farmer 1 already has id=1 qty=8000 and id=7 qty=1000) ──
    (5, "maize",    50, 31,  14),   # Kwame  Ejisu          — 2 weeks
    (3, "maize",    80, 13,  25),   # Ama    Ahafo-Ano      — 25 days
    (9, "maize",    35, 30,  45),   # Kojo   Bosomtwe       — 45 days

    # ── TOMATO (farmer 1 has id=2 qty=5000) ──
    (4, "tomato",   40, 34,   5),   # Abena  Kumasi         — URGENT 5 days
    (7, "tomato",   25, 29,  18),   # Kwabena Bosome Freho
    (8, "tomato",   30, 33,  30),   # Adwoa  Juaben

    # ── ONION (farmer 1 has id=3 qty=3000) ──
    (5, "onion",    45, 20,  10),   # Kwame  Asante-Akim — using district 20
    (7, "onion",    20, 29,  35),   # Kwabena Bosome Freho
    (9, "onion",    60, 30,  20),   # Kojo   Bosomtwe

    # ── CASSAVA ──
    (5, "cassava",  70, 31,   8),   # Kwame  Ejisu         — nearly ready
    (6, "cassava",  55, 28,  22),   # Yaw    Bekwai
    (3, "cassava",  90, 13,  40),   # Ama    Ahafo-Ano
    (8, "cassava",  40, 33,  15),   # Adwoa  Juaben

    # ── RICE ──
    (1, "rice",     60, 20,  12),   # Akosua Asante-Akim
    (6, "rice",     80, 28,  28),   # Yaw    Bekwai
    (9, "rice",     45, 30,  50),   # Kojo   Bosomtwe
    (4, "rice",     35, 34,  20),   # Abena  Kumasi

    # ── PLANTAIN ──
    (6, "plantain", 50, 28,   7),   # Yaw    Bekwai         — URGENT 7 days
    (3, "plantain", 65, 13,  19),   # Ama    Ahafo-Ano
    (8, "plantain", 30, 33,  33),   # Adwoa  Juaben
    (5, "plantain", 40, 31,  14),   # Kwame  Ejisu
]


def build_farmer_ids() -> list[int]:
    """Return ordered list of farmer IDs. Insert new farmers if not present."""
    # Start with the 4 known existing farmers in ID order
    ids: list[int] = [1, 2, 3, 4]

    with get_session() as db:
        for full_name, phone, district_id in NEW_FARMERS:
            existing = db.execute(
                text("SELECT id FROM farmers WHERE phone_number = :p"),
                {"p": phone}
            ).fetchone()
            if existing:
                ids.append(existing[0])
                print(f"  [skip] {full_name} already exists (id={existing[0]})")
                continue
            row = db.execute(
                text("""
                    INSERT INTO farmers (full_name, phone_number, district_id, registered_by, is_active)
                    VALUES (:n, :p, :d, NULL, true)
                    RETURNING id
                """),
                {"n": full_name, "p": phone, "d": district_id}
            ).fetchone()
            db.commit()
            ids.append(row[0])
            print(f"  [+] Farmer {full_name} -> id={row[0]}")

    return ids


def existing_declarations() -> set[tuple]:
    """Return set of (farmer_id, crop, district_id) already active in DB."""
    with get_session() as db:
        rows = db.execute(
            text("SELECT farmer_id, crop, district_id FROM farmer_declarations WHERE status='active'")
        ).fetchall()
    return {(r[0], r[1], r[2]) for r in rows}


def create_declaration(farmer_id: int, crop: str, quantity_bags: int,
                        district_id: int, days_until: int) -> int | None:
    harvest_date = (date.today() + timedelta(days=days_until)).isoformat()
    byproducts = [
        {
            "type":        bt,
            "quantity_kg": round(quantity_bags * 100 * ratio, 1),
        }
        for bt, ratio, _ in BYPRODUCTS.get(crop, [])
    ]
    payload = {
        "farmer_id":     farmer_id,
        "crop":          crop,
        "quantity_bags": quantity_bags,
        "district_id":   district_id,
        "harvest_date":  harvest_date,
        "source":        "seed",
        "byproducts":    byproducts,
    }
    try:
        r = requests.post(f"{API}/api/declarations", json=payload, timeout=60)
        if r.status_code in (200, 201):
            decl_id = r.json().get("declaration_id")
            print(f"  [+] {crop:10s} farmer={farmer_id} dist={district_id} {quantity_bags}bags harvest={harvest_date} -> decl id={decl_id}")
            return decl_id
        else:
            print(f"  [!] {crop} farmer={farmer_id} FAILED {r.status_code}: {r.text[:120]}")
            return None
    except Exception as e:
        print(f"  [!] {crop} farmer={farmer_id} ERROR: {e}")
        return None


def main():
    print("\n=== AgriMatch Demo Seed ===\n")

    print("Step 1: Farmers...")
    farmer_ids = build_farmer_ids()
    print(f"  Farmer ID map: {farmer_ids}\n")

    print(f"Step 2: Creating {len(DECLARATIONS)} declarations...")
    seen = existing_declarations()
    created = skipped = 0

    for farmer_idx, crop, qty_bags, district_id, days in DECLARATIONS:
        if farmer_idx >= len(farmer_ids):
            print(f"  [!] farmer_idx={farmer_idx} out of range (have {len(farmer_ids)}), skipping")
            continue
        fid = farmer_ids[farmer_idx]
        if (fid, crop, district_id) in seen:
            print(f"  [skip] farmer={fid} {crop} district={district_id} already exists")
            skipped += 1
            continue
        result = create_declaration(fid, crop, qty_bags, district_id, days)
        if result:
            seen.add((fid, crop, district_id))
            created += 1

    print(f"\n=== Done: {created} created, {skipped} skipped ===")
    print("\nURLs to visit:")
    print("  http://localhost:3001/shop         (click each crop tab)")
    print("  http://localhost:3001/shop/1       (product detail)")
    print("  http://localhost:3001/seller       (seller dashboard + strategies)")
    print("  http://localhost:3001/seller/listings")
    print("  http://localhost:3001/byproducts")


if __name__ == "__main__":
    main()
