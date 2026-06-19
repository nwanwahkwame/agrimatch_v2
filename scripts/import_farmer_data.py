"""
Import data/Farmer_data.xlsx into the AgriMatch database.

194 farmers:
  - 30 from Builsa North, Upper East  (district_id=200)
  - 164 from Shai Osudoku, Greater Accra (district_id=153)

Run from project root (DATABASE_URL must be set):
  $env:DATABASE_URL = "postgresql://postgres:...@zephyr.proxy.rlwy.net:32010/railway"
  python scripts/import_farmer_data.py
"""
import os, sys, requests, re
import pandas as pd
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_session
from sqlalchemy import text

API = os.getenv("API_URL", "https://agrimatch-production.up.railway.app")

# ── District mapping: file text → district_id ─────────────────────────────────
DISTRICT_ID = {
    "BUILSA NORTH":     200,   # Upper East
    "SHIA - OSUKODU":  153,   # Shai Osudoku, Greater Accra
    "SHIA-OSUKODU":    153,
    "SHAI OSUDOKU":    153,
    "SHAI-OSUDOKU":    153,
}

# ── Crop name normalisation ───────────────────────────────────────────────────
CROP_MAP = {
    "MAIZE":       "maize",
    "RICE":        "rice",
    "GROUNDNUT":   "groundnut",
    "TOMATO":      "tomato",
    "TOMATOES":    "tomato",
    "CASSAVA":     "cassava",
    "ONION":       "onion",
    "SORGUM":      "sorghum",
    "SORGHUM":     "sorghum",
    "PEPPER":      "pepper",
    "SOYA":        "soybean",
    "SOYA BEANS":  "soybean",
    "SOYABEAN":    "soybean",
    "SOYABEANS":   "soybean",
    "OKRO":        None,   # no price data in HDX/MoFA — skipped
    "POTATO":      None,   # no price data in HDX/MoFA — skipped
}

# ── Month text → number ───────────────────────────────────────────────────────
MONTH_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

BYPRODUCTS = {
    "maize":     [("husks", 0.30, False), ("cobs", 0.20, False)],
    "tomato":    [("damaged fruit", 0.10, True)],
    "onion":     [("outer skins", 0.08, False)],
    "cassava":   [("peels", 0.12, True)],
    "rice":      [("bran", 0.15, False), ("husks", 0.20, False)],
    "groundnut": [("shells", 0.10, False)],
    "sorghum":   [("stalks", 0.15, False)],
}


def parse_phone(raw) -> str | None:
    """Normalise to 10-digit Ghana number starting with 0."""
    s = str(raw).strip().replace(" ", "").replace("-", "")
    if s.startswith("+233"):
        s = "0" + s[4:]
    elif s.startswith("233") and len(s) == 12:
        s = "0" + s[3:]
    elif len(s) == 9:
        s = "0" + s
    return s if len(s) == 10 and s.isdigit() else None


def parse_crops(raw) -> list[str]:
    """Split 'MAIZE/GROUNDNUT' into ['maize', 'groundnut'], skip unknowns."""
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return []
    parts = re.split(r"[/,&+]", str(raw).upper())
    result = []
    for p in parts:
        p = p.strip()
        mapped = CROP_MAP.get(p)
        if mapped:
            if mapped not in result:
                result.append(mapped)
        elif p:
            pass  # silently skip crops not in crop_reference
    return result


def parse_harvest_date(raw) -> date | None:
    """Extract the first month name and return 15th of that month in 2026/2027."""
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).lower()
    today = date.today()
    for abbr, num in MONTH_NUM.items():
        if abbr in s:
            yr = today.year
            d = date(yr, num, 15)
            if d < today:          # already passed this year → push to next
                d = date(yr + 1, num, 15)
            return d
    return None


def district_id_for(raw_district: str) -> int | None:
    key = str(raw_district).strip().upper()
    return DISTRICT_ID.get(key)


# ── Load spreadsheet ──────────────────────────────────────────────────────────

def load_data():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "Farmer_data.xlsx")
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    return df


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_or_create_farmer(name: str, phone: str, district_id: int) -> int | None:
    with get_session() as db:
        row = db.execute(
            text("SELECT id FROM farmers WHERE phone_number = :p"),
            {"p": phone}
        ).fetchone()
        if row:
            return row[0]
        new = db.execute(
            text("""
                INSERT INTO farmers (full_name, phone_number, district_id, is_active)
                VALUES (:n, :p, :d, true) RETURNING id
            """),
            {"n": name.strip().title(), "p": phone, "d": district_id}
        ).fetchone()
        db.commit()
        return new[0] if new else None


def existing_decls() -> set[tuple]:
    with get_session() as db:
        rows = db.execute(
            text("SELECT farmer_id, crop, district_id FROM farmer_declarations WHERE status='active'")
        ).fetchall()
    return {(r[0], r[1], r[2]) for r in rows}


def create_declaration(farmer_id: int, crop: str, district_id: int,
                        harvest: date, qty_bags: int = 30) -> bool:
    byproducts = [
        {"type": bt, "quantity_kg": round(qty_bags * 100 * ratio, 1)}
        for bt, ratio, _ in BYPRODUCTS.get(crop, [])
    ]
    try:
        r = requests.post(f"{API}/api/declarations", json={
            "farmer_id":     farmer_id,
            "crop":          crop,
            "quantity_bags": qty_bags,
            "district_id":   district_id,
            "harvest_date":  harvest.isoformat(),
            "source":        "farmer_data_import",
            "byproducts":    byproducts,
        }, timeout=60)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"    API error: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n=== AgriMatch Farmer Data Import ===")
    print(f"API: {API}\n")

    df = load_data()
    print(f"Loaded {len(df)} rows from Farmer_data.xlsx\n")

    seen_decls  = existing_decls()
    skipped_ph  = skipped_dist = created_f = created_d = skipped_d = 0

    for _, row in df.iterrows():
        name    = str(row["Name"]).strip()
        phone   = parse_phone(row["Telephone No."])
        district_id = district_id_for(str(row["District"]).strip())
        harvest = parse_harvest_date(row["Harvest Date"])

        # Collect all crops from both columns
        all_crops = (
            parse_crops(row.get("Crops planted")) +
            parse_crops(row.get("Yet to plant"))
        )
        # Deduplicate preserving order
        seen_c: list[str] = []
        [seen_c.append(c) for c in all_crops if c not in seen_c]
        all_crops = seen_c

        # Validate
        if not phone:
            print(f"  [!] Bad phone for {name}: {row['Telephone No.']} — skip")
            skipped_ph += 1
            continue
        if not district_id:
            print(f"  [!] Unknown district '{row['District']}' for {name} — skip")
            skipped_dist += 1
            continue
        if not harvest:
            harvest = date(2026, 11, 15)   # default: November 2026

        # Ensure farmer exists
        farmer_id = get_or_create_farmer(name, phone, district_id)
        if not farmer_id:
            print(f"  [!] Could not insert {name}")
            continue

        is_new_farmer = True
        for crop in all_crops:
            key = (farmer_id, crop, district_id)
            if key in seen_decls:
                skipped_d += 1
                continue
            if create_declaration(farmer_id, crop, district_id, harvest):
                print(f"  [+] {name:35s} {crop:12s} dist={district_id} harvest={harvest}")
                seen_decls.add(key)
                created_d += 1
                if is_new_farmer:
                    created_f += 1
                    is_new_farmer = False
            else:
                print(f"  [!] Failed declaration for {name} — {crop}")

        if not all_crops:
            print(f"  [-] {name:35s} no mappable crops — farmer registered only")

    print(f"""
=== Import complete ===
  Farmers created/updated : {created_f}
  Declarations created    : {created_d}
  Declarations skipped    : {skipped_d} (already exist)
  Skipped (bad phone)     : {skipped_ph}
  Skipped (unknown dist)  : {skipped_dist}
""")


if __name__ == "__main__":
    main()
