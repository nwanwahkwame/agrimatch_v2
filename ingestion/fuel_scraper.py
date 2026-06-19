"""
M4 fuel price scraper for AgriMatch.

Fetches current petrol, diesel, and LPG prices from the NPA Ghana website.
Falls back to the latest manually-verified seed values if the page cannot
be parsed, and flags the source accordingly so operators know to update.
"""

import logging
import re
from datetime import date
from typing import Optional

import requests
from sqlalchemy import text

from db.connection import get_session

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

NPA_URL = "https://www.npa.gov.gh/"
REQUEST_TIMEOUT = 15  # seconds

# Last manually-verified NPA published prices (October 2023).
# Update these when the scraper cannot reach the site and a manual check
# is performed.
_MANUAL_SEED = {
    "petrol": 14.34,
    "diesel": 14.17,
    "LPG":    9.50,   # GHS per kg (NPA publishes LPG per kg, not per litre)
}

_FUEL_KEYWORDS = {
    "petrol":  ["petrol", "gasoline", "premium"],
    "diesel":  ["diesel", "gasoil"],
    "LPG":     ["lpg", "liquefied petroleum", "cooking gas"],
}

# GHS price plausibility window (avoids picking up table indices, dates, etc.)
_PRICE_MIN = 1.0
_PRICE_MAX = 50.0


# ── Scraper ───────────────────────────────────────────────────────────────────

class FuelScraper:

    def scrape_npa(self) -> list[dict]:
        """
        Fetch current fuel prices from the NPA Ghana website.

        Tries to parse petrol / diesel / LPG prices from the live page.
        Returns a list of price dicts; source is 'npa' on success or
        'npa_manual_seed' when the page cannot be parsed.
        """
        prices = self._fetch_and_parse()
        if prices and len(prices) >= 2:
            logger.info("NPA scrape succeeded: %d fuel types found", len(prices))
            return prices

        logger.warning(
            "NPA scrape could not extract prices — falling back to manual seed. "
            "Visit %s and update _MANUAL_SEED in fuel_scraper.py if prices changed.",
            NPA_URL,
        )
        today = date.today()
        return [
            {
                "fuel_type":           ft,
                "price_ghs_per_litre": price,
                "price_date":          today,
                "source":              "npa_manual_seed",
            }
            for ft, price in _MANUAL_SEED.items()
        ]

    def _fetch_and_parse(self) -> list[dict]:
        """Return parsed prices or [] if parsing fails for any reason."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("beautifulsoup4 not installed; cannot parse NPA page")
            return []

        try:
            resp = requests.get(
                NPA_URL,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AgriMatch/1.0)"},
                verify=True,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("NPA HTTP request failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        today = date.today()
        found: dict[str, float] = {}

        # Strategy 1: look for tables whose rows mention a fuel keyword
        for table in soup.find_all("table"):
            text_lower = table.get_text(" ", strip=True).lower()
            has_fuel = any(
                any(kw in text_lower for kw in kws)
                for kws in _FUEL_KEYWORDS.values()
            )
            if not has_fuel:
                continue
            for row in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                row_text = " ".join(cells).lower()
                for fuel_type, keywords in _FUEL_KEYWORDS.items():
                    if fuel_type in found:
                        continue
                    if any(kw in row_text for kw in keywords):
                        price = _extract_price(cells)
                        if price is not None:
                            found[fuel_type] = price

        # Strategy 2: scan all text nodes for price patterns near fuel names
        if len(found) < 2:
            full_text = soup.get_text(" ", strip=True)
            for fuel_type, keywords in _FUEL_KEYWORDS.items():
                if fuel_type in found:
                    continue
                for kw in keywords:
                    pattern = rf"{re.escape(kw)}[^.]*?(\d+\.\d{{1,3}})"
                    m = re.search(pattern, full_text, re.IGNORECASE)
                    if m:
                        val = float(m.group(1))
                        if _PRICE_MIN <= val <= _PRICE_MAX:
                            found[fuel_type] = val
                            break

        return [
            {
                "fuel_type":           ft,
                "price_ghs_per_litre": price,
                "price_date":          today,
                "source":              "npa",
            }
            for ft, price in found.items()
        ]

    def save_to_database(self, prices: list[dict]) -> int:
        """
        Upsert fuel prices with ON CONFLICT DO NOTHING.
        Returns the number of rows actually inserted.
        """
        if not prices:
            return 0

        inserted = 0
        with get_session() as db:
            for p in prices:
                result = db.execute(
                    text("""
                        INSERT INTO fuel_prices
                            (price_date, fuel_type, price_ghs_per_litre, source)
                        VALUES (:price_date, :fuel_type, :price, :source)
                        ON CONFLICT (price_date, fuel_type) DO NOTHING
                    """),
                    {
                        "price_date": p["price_date"],
                        "fuel_type":  p["fuel_type"],
                        "price":      p["price_ghs_per_litre"],
                        "source":     p.get("source", "npa"),
                    },
                )
                inserted += result.rowcount

        logger.info("fuel_prices: inserted %d / %d rows", inserted, len(prices))
        return inserted

    def get_latest_prices(self) -> dict[str, Optional[float]]:
        """Return the most recent price for each fuel type."""
        with get_session() as db:
            rows = db.execute(
                text("""
                    SELECT DISTINCT ON (fuel_type)
                        fuel_type, price_ghs_per_litre
                    FROM fuel_prices
                    ORDER BY fuel_type, price_date DESC
                """)
            ).fetchall()
        return {r[0]: float(r[1]) for r in rows}

    def get_price_on_date(self, target_date: date) -> dict[str, Optional[float]]:
        """
        Return the closest price on or before target_date for each fuel type.
        Used by M8 logistics cost model for historical delivery cost calculation.
        """
        with get_session() as db:
            rows = db.execute(
                text("""
                    SELECT DISTINCT ON (fuel_type)
                        fuel_type, price_ghs_per_litre, price_date
                    FROM fuel_prices
                    WHERE price_date <= :d
                    ORDER BY fuel_type, price_date DESC
                """),
                {"d": target_date},
            ).fetchall()
        return {r[0]: float(r[1]) for r in rows}

    def run(self) -> dict:
        """Scrape NPA, save to DB, log result. Returns summary dict."""
        prices = self.scrape_npa()
        inserted = self.save_to_database(prices)

        sources = list({p["source"] for p in prices})
        summary = {
            "source":        "fuel_scraper",
            "rows_fetched":  len(prices),
            "rows_inserted": inserted,
            "rows_clean":    inserted,
            "fuel_sources":  sources,
            "status":        "success",
        }

        with get_session() as db:
            db.execute(
                text("""
                    INSERT INTO ingestion_log
                        (source, status, rows_fetched, rows_clean, rows_quarantined)
                    VALUES (:src, :status, :fetched, :clean, 0)
                """),
                {
                    "src":     "fuel_scraper",
                    "status":  "success",
                    "fetched": len(prices),
                    "clean":   inserted,
                },
            )

        logger.info("FuelScraper.run() complete: %s", summary)
        return summary


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_price(cells: list[str]) -> Optional[float]:
    """Return the first plausible GHS price found in a list of cell strings."""
    for cell in cells:
        m = re.search(r"(\d{1,2}\.\d{1,3})", cell.replace(",", ""))
        if m:
            val = float(m.group(1))
            if _PRICE_MIN <= val <= _PRICE_MAX:
                return val
    return None
