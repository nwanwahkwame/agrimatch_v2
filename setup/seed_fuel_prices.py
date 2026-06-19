"""
Seed 5 years of approximate monthly fuel prices for Ghana (2019-2023).

Uses known annual average GHS prices per litre interpolated month-by-month
so M8 has historical cost data immediately without waiting for weekly scrapes.

Usage (from project root):
    python setup/seed_fuel_prices.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Historical annual averages (GHS per litre) ────────────────────────────────
# Sources: NPA published price history, GhanaWeb, World Bank Ghana data
# LPG is published per kg by NPA; converted here to approximate GHS/litre
# equivalent for table consistency (1 kg LPG ~ 1.96 litres).

_ANNUAL = {
    2019: {"petrol": 4.54,  "diesel": 4.67},
    2020: {"petrol": 4.41,  "diesel": 4.55},
    2021: {"petrol": 5.97,  "diesel": 5.84},
    2022: {"petrol": 11.32, "diesel": 11.67},
    2023: {"petrol": 13.89, "diesel": 14.12},
}

# LPG follows petrol at roughly 62-65% (price per litre-equivalent)
_LPG_FACTOR = 0.63


def _interp(year: int, month: int, fuel: str) -> float:
    """
    Linearly interpolate a monthly price from annual averages.

    Annual averages are treated as the mid-year value (July).
    Months before 2019-Jul use the 2019 average; months after
    2023-Jul use the 2023 average.
    """
    # Fractional year position for this month (mid-month)
    x = year + (month - 0.5) / 12

    # Build sorted (x_midyear, price) anchor points
    if fuel == "LPG":
        anchors = [(y + 0.5, round(v["petrol"] * _LPG_FACTOR, 3))
                   for y, v in sorted(_ANNUAL.items())]
    else:
        anchors = [(y + 0.5, v[fuel]) for y, v in sorted(_ANNUAL.items())]

    if x <= anchors[0][0]:
        return anchors[0][1]
    if x >= anchors[-1][0]:
        return anchors[-1][1]

    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 3)

    return anchors[-1][1]


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print()
    print("Connecting to Railway PostgreSQL ...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print("Seeding monthly fuel prices 2019-2023 ...")
    rows_attempted = 0
    rows_inserted  = 0

    with conn.cursor() as cur:
        for year in range(2019, 2024):
            for month in range(1, 13):
                price_date = f"{year}-{month:02d}-01"
                for fuel in ("petrol", "diesel", "LPG"):
                    price = _interp(year, month, fuel)
                    cur.execute(
                        """
                        INSERT INTO fuel_prices
                            (price_date, fuel_type, price_ghs_per_litre, source)
                        VALUES (%s, %s, %s, 'historical_seed')
                        ON CONFLICT (price_date, fuel_type) DO NOTHING
                        """,
                        (price_date, fuel, price),
                    )
                    rows_attempted += 1
                    rows_inserted  += cur.rowcount

    conn.commit()
    print(f"  Attempted: {rows_attempted}  Inserted: {rows_inserted}  Skipped (existing): {rows_attempted - rows_inserted}")

    print()
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fuel_prices")
        total = cur.fetchone()[0]
        cur.execute("SELECT MIN(price_date), MAX(price_date) FROM fuel_prices")
        mn, mx = cur.fetchone()
        print(f"  Total rows   : {total:,}")
        print(f"  Date range   : {mn} to {mx}")
        print()
        print(f"  {'Fuel':<10} {'Min GHS':>10} {'Max GHS':>10} {'Latest GHS':>12}")
        print("  " + "-" * 46)
        cur.execute("""
            SELECT fuel_type,
                   MIN(price_ghs_per_litre),
                   MAX(price_ghs_per_litre),
                   (SELECT price_ghs_per_litre FROM fuel_prices fp2
                    WHERE fp2.fuel_type = fuel_prices.fuel_type
                    ORDER BY price_date DESC LIMIT 1)
            FROM fuel_prices
            GROUP BY fuel_type
            ORDER BY fuel_type
        """)
        for r in cur.fetchall():
            print(f"  {r[0]:<10} {float(r[1]):>10.3f} {float(r[2]):>10.3f} {float(r[3]):>12.3f}")

    conn.close()
    print()


if __name__ == "__main__":
    main()
