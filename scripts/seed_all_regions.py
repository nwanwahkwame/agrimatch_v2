"""
Seed farmers and declarations across ALL regions of Ghana.

Run against Railway:
  1. Get DATABASE_URL from Railway -> heartfelt-reflection -> Connect tab
  2. In PowerShell:
       $env:DATABASE_URL = "postgresql://postgres:...@zephyr.proxy.rlwy.net:32010/railway"
       python scripts/seed_all_regions.py

The script skips records that already exist (safe to re-run).
"""
import os, sys, requests
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_session
from sqlalchemy import text

API = os.getenv("API_URL", "https://agrimatch-production.up.railway.app")

# ── Farmers: 2-3 per region, spread across Ghana ──────────────────────────────
# (full_name, phone, district_id, region_label)
FARMERS = [
    # Ashanti (already seeded — kept for reference, will be skipped)
    ("Kofi Mensah",        "0244000001", 34,  "Ashanti"),
    ("Akosua Boateng",     "0244000002", 34,  "Ashanti"),

    # Northern
    ("Ibrahim Alhassan",   "0244000011", 174, "Northern"),  # Tamale
    ("Fatima Zakaria",     "0244000012", 163, "Northern"),  # Gushegu
    ("Sumaila Issah",      "0244000013", 166, "Northern"),  # Kumbungu

    # Greater Accra
    ("Efua Quartey",       "0244000014", 131, "Greater Accra"),  # Accra
    ("Nii Odoi Mensah",    "0244000015", 149, "Greater Accra"),  # La-Nkwantanang

    # Eastern
    ("Yaw Darko",          "0244000016", 121, "Eastern"),  # Nsawam
    ("Abena Ofori",        "0244000017", 112, "Eastern"),  # Kwaebibirem
    ("Kofi Nkrumah",       "0244000018", 95,  "Eastern"),  # Abuakwa North

    # Volta
    ("Kafui Agbeko",       "0244000019", 227, "Volta"),  # Ho Municipal
    ("Edem Avuletey",      "0244000020", 229, "Volta"),  # Hohoe
    ("Abla Dzakpasu",      "0244000021", 223, "Volta"),  # Akatsi North

    # Bono
    ("Kwabena Takyi",      "0244000022", 58,  "Bono"),   # Sunyani
    ("Akua Ampem",         "0244000023", 61,  "Bono"),   # Wenchi

    # Bono East
    ("Yaw Acheampong",     "0244000024", 71,  "Bono East"),  # Techiman
    ("Afia Konadu",        "0244000025", 62,  "Bono East"),  # Atebubu-Amantin

    # Upper East
    ("Asana Atia",         "0244000026", 198, "Upper East"),  # Bolgatanga
    ("Azara Mohammed",     "0244000027", 194, "Upper East"),  # Bawku

    # Upper West
    ("Hawa Saaka",         "0244000028", 218, "Upper West"),  # Wa Municipal
    ("Baba Seidu",         "0244000029", 219, "Upper West"),  # Wa West

    # Oti
    ("Comfort Agbevivi",   "0244000030", 185, "Oti"),  # Nkwanta North

    # Central
    ("Ama Entsua",         "0244000031", 73,  "Central"),  # Abura-Asebu

    # Western
    ("Ekow Eshun",         "0244000032", 247, "Western"),  # Tarkwa

    # North East
    ("Dramani Yakubu",     "0244000033", 157, "North East"),  # Bunkpurugu
]

# ── Declarations: crop + district + days until harvest ────────────────────────
# (phone, crop, quantity_bags, district_id, days_until_harvest)
DECLARATIONS = [
    # Northern — maize, sorghum, cowpea, groundnut
    ("0244000011", "maize",     80,  174, 20),
    ("0244000011", "sorghum",   60,  174, 35),
    ("0244000012", "cowpea",    40,  163, 15),
    ("0244000012", "maize",     50,  163, 28),
    ("0244000013", "groundnut", 70,  166, 22),
    ("0244000013", "cowpea",    45,  166, 30),

    # Greater Accra — tomato, onion
    ("0244000014", "tomato",    35,  131, 8),
    ("0244000014", "onion",     50,  131, 18),
    ("0244000015", "tomato",    25,  149, 12),
    ("0244000015", "cassava",   60,  149, 40),

    # Eastern — cassava, plantain, maize
    ("0244000016", "cassava",   90,  121, 20),
    ("0244000016", "plantain",  55,  121, 14),
    ("0244000017", "maize",     70,  112, 25),
    ("0244000017", "cassava",   80,  112, 35),
    ("0244000018", "plantain",  40,  95,  10),
    ("0244000018", "yam",       60,  95,  45),

    # Volta — yam, cassava, rice
    ("0244000019", "yam",       75,  227, 30),
    ("0244000019", "cassava",   55,  227, 20),
    ("0244000020", "rice",      65,  229, 18),
    ("0244000020", "plantain",  45,  229, 12),
    ("0244000021", "yam",       50,  223, 40),
    ("0244000021", "tomato",    30,  223, 7),

    # Bono — maize, cassava, groundnut
    ("0244000022", "maize",     100, 58,  22),
    ("0244000022", "groundnut", 55,  58,  28),
    ("0244000023", "cassava",   80,  61,  35),
    ("0244000023", "maize",     60,  61,  18),

    # Bono East — yam, maize, sorghum
    ("0244000024", "yam",       90,  71,  40),
    ("0244000024", "maize",     70,  71,  15),
    ("0244000025", "sorghum",   50,  62,  30),
    ("0244000025", "groundnut", 40,  62,  20),

    # Upper East — sorghum, cowpea, groundnut
    ("0244000026", "sorghum",   80,  198, 25),
    ("0244000026", "cowpea",    60,  198, 18),
    ("0244000027", "groundnut", 70,  194, 22),
    ("0244000027", "sorghum",   55,  194, 35),

    # Upper West — sorghum, groundnut, cowpea
    ("0244000028", "sorghum",   65,  218, 28),
    ("0244000028", "cowpea",    50,  218, 20),
    ("0244000029", "groundnut", 60,  219, 30),
    ("0244000029", "yam",       45,  219, 45),

    # Oti — yam, cassava
    ("0244000030", "yam",       80,  185, 35),
    ("0244000030", "cassava",   55,  185, 22),

    # Central — cassava, tomato, plantain
    ("0244000031", "cassava",   70,  73,  25),
    ("0244000031", "tomato",    40,  73,  10),

    # Western — plantain, cassava
    ("0244000032", "plantain",  75,  247, 18),
    ("0244000032", "cassava",   60,  247, 28),

    # North East — sorghum, cowpea
    ("0244000033", "sorghum",   55,  157, 30),
    ("0244000033", "cowpea",    45,  157, 22),
]

BYPRODUCTS = {
    "maize":    [("husks", 0.30, False), ("cobs", 0.20, False)],
    "tomato":   [("damaged fruit", 0.10, True)],
    "onion":    [("outer skins", 0.08, False)],
    "cassava":  [("peels", 0.12, True)],
    "rice":     [("bran", 0.15, False), ("husks", 0.20, False)],
    "plantain": [("peels", 0.10, True)],
    "cowpea":   [("pods", 0.08, False)],
    "groundnut":[("shells", 0.10, False)],
    "sorghum":  [("stalks", 0.15, False)],
    "yam":      [("peels", 0.05, True)],
}


def ensure_farmers() -> dict[str, int]:
    """Insert farmers that don't exist yet. Returns phone -> id map."""
    phone_to_id: dict[str, int] = {}
    with get_session() as db:
        for name, phone, district_id, region in FARMERS:
            row = db.execute(
                text("SELECT id FROM farmers WHERE phone_number = :p"),
                {"p": phone}
            ).fetchone()
            if row:
                phone_to_id[phone] = row[0]
                print(f"  [skip] {name} ({region}) — already exists id={row[0]}")
            else:
                new = db.execute(
                    text("""
                        INSERT INTO farmers (full_name, phone_number, district_id, is_active)
                        VALUES (:n, :p, :d, true) RETURNING id
                    """),
                    {"n": name, "p": phone, "d": district_id}
                ).fetchone()
                db.commit()
                phone_to_id[phone] = new[0]
                print(f"  [+] {name} ({region}) -> id={new[0]}")
    return phone_to_id


def existing_decls() -> set[tuple]:
    with get_session() as db:
        rows = db.execute(
            text("SELECT farmer_id, crop, district_id FROM farmer_declarations WHERE status='active'")
        ).fetchall()
    return {(r[0], r[1], r[2]) for r in rows}


def create_declaration(farmer_id: int, crop: str, qty_bags: int,
                        district_id: int, days: int) -> bool:
    byproducts = [
        {"type": bt, "quantity_kg": round(qty_bags * 100 * ratio, 1)}
        for bt, ratio, _ in BYPRODUCTS.get(crop, [])
    ]
    harvest_date = (date.today() + timedelta(days=days)).isoformat()
    try:
        r = requests.post(f"{API}/api/declarations", json={
            "farmer_id":     farmer_id,
            "crop":          crop,
            "quantity_bags": qty_bags,
            "district_id":   district_id,
            "harvest_date":  harvest_date,
            "source":        "seed_regions",
            "byproducts":    byproducts,
        }, timeout=60)
        if r.status_code in (200, 201):
            decl_id = r.json().get("declaration_id")
            print(f"  [+] farmer={farmer_id} {crop:10s} {qty_bags}bags dist={district_id} -> decl={decl_id}")
            return True
        else:
            print(f"  [!] {crop} farmer={farmer_id} FAILED {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        print(f"  [!] ERROR: {e}")
        return False


def main():
    print(f"\n=== AgriMatch Multi-Region Seed ===")
    print(f"API: {API}\n")

    print("Step 1: Ensuring farmers exist across all regions...")
    phone_to_id = ensure_farmers()
    print(f"  {len(phone_to_id)} farmers ready\n")

    print("Step 2: Creating declarations...")
    seen  = existing_decls()
    added = skipped = 0

    for phone, crop, qty_bags, district_id, days in DECLARATIONS:
        fid = phone_to_id.get(phone)
        if not fid:
            print(f"  [!] No farmer found for phone {phone}")
            continue
        if (fid, crop, district_id) in seen:
            print(f"  [skip] farmer={fid} {crop} dist={district_id} exists")
            skipped += 1
            continue
        if create_declaration(fid, crop, qty_bags, district_id, days):
            seen.add((fid, crop, district_id))
            added += 1

    print(f"\n=== Done: {added} created, {skipped} skipped ===")


if __name__ == "__main__":
    main()
