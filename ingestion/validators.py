"""
Row-level validation for raw price data from HDX and MoFA sources.

Validation is intentionally strict: any ambiguity (missing field, unparseable
date, implausible price) results in rejection.  Rejected rows are written to
the price_quarantine table for human review rather than silently dropped.
"""

import logging
from datetime import date, datetime
from typing import Any

from config.settings import USD_TO_GHS_RATE
from config.unit_map import UNIT_MAP

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_VALID_CURRENCIES = {"GHS", "USD"}

# Prices above this are almost certainly data-entry errors (e.g. GHS 999999)
_MAX_PRICE_RAW = 100_000.0

# Price per kg in GHS above this signals a unit error (e.g. price recorded
# per 100 kg bag but unit left as "KG")
_MAX_PRICE_PER_KG_GHS = 5_000.0

# For each logical field, the column names we accept in priority order.
# The first key found in the row dict is used.
_FIELD_CANDIDATES: dict[str, list[str]] = {
    "date":      ["date", "price_date", "survey_date", "period", "month"],
    "market":    ["market", "market_name", "location", "site", "market_id"],
    "commodity": ["commodity", "crop", "product", "item", "commodity_name"],
    "price":     ["price", "price_ghs", "amount", "value"],
    "currency":  ["currency", "currency_code"],
    "unit":      ["unit", "unit_of_measure", "measure"],
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_field(row: dict, logical_name: str) -> tuple[str | None, Any]:
    """Return *(actual_key, value)* for the first matching candidate, else *(None, None)*."""
    for key in _FIELD_CANDIDATES.get(logical_name, [logical_name]):
        if key in row:
            return key, row[key]
    return None, None


def _parse_date(value: Any) -> date | None:
    """Return a ``date`` from *value* or ``None`` if unparseable.

    Handles:
    - Strings in ``YYYY-MM-DD`` (or ``YYYY-MM-DD HH:MM:SS``) format
    - Integers / floats that are Unix timestamps in **milliseconds**
      (produced by ``df.to_json()`` when the column is datetime64)
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.utcfromtimestamp(float(value) / 1000).date()
        except (ValueError, OSError):
            return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> float | None:
    """Return *value* as a float, or ``None`` if conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def validate_row(row_dict: dict, source: str) -> tuple[bool, str | None]:
    """Validate a single raw price row.

    Parameters
    ----------
    row_dict:
        A plain Python dict representing one row of raw data.
    source:
        The data source identifier, e.g. ``'hdx'`` or ``'mofa'``.

    Returns
    -------
    (True, None)
        Row passed all checks.
    (False, reason)
        Row failed; *reason* is a plain-English string explaining the first
        failing check.  Only the first failure is returned so the quarantine
        message stays concise.
    """

    logger.debug("Validating row from source '%s'", source)

    # ── Schema checks ─────────────────────────────────────────────────────────

    # 1. date — must exist and be parseable
    _, raw_date = _find_field(row_dict, "date")
    if raw_date is None or str(raw_date).strip() == "":
        return False, "Missing 'date' field"
    parsed_date = _parse_date(raw_date)
    if parsed_date is None:
        return False, (
            f"'date' value '{raw_date}' cannot be parsed — expected YYYY-MM-DD"
        )

    # 2. market — must exist and be non-empty
    market_key, market_val = _find_field(row_dict, "market")
    if market_key is None or not str(market_val or "").strip():
        return False, "Missing or empty 'market' field"

    # 3. commodity — must exist and be non-empty
    commodity_key, commodity_val = _find_field(row_dict, "commodity")
    if commodity_key is None or not str(commodity_val or "").strip():
        return False, "Missing or empty 'commodity' field"

    # 4. price — must exist, be numeric, and be positive
    price_key, raw_price = _find_field(row_dict, "price")
    if price_key is None or raw_price is None:
        return False, "Missing 'price' field"
    price = _to_float(raw_price)
    if price is None:
        return False, f"'price' value '{raw_price}' is not a number"
    if price <= 0:
        return False, f"'price' must be greater than zero (got {price})"

    # 5. currency — must exist and be GHS or USD
    _, raw_currency = _find_field(row_dict, "currency")
    if not raw_currency or not str(raw_currency).strip():
        return False, "Missing 'currency' field"
    currency = str(raw_currency).strip().upper()
    if currency not in _VALID_CURRENCIES:
        return False, (
            f"'currency' must be GHS or USD (got '{raw_currency}')"
        )

    # 6. unit — must exist and be non-empty
    _, raw_unit = _find_field(row_dict, "unit")
    if not raw_unit or not str(raw_unit).strip():
        return False, "Missing or empty 'unit' field"

    # ── Domain checks ─────────────────────────────────────────────────────────

    # 7. price date must not be in the future
    if parsed_date > date.today():
        return False, (
            f"Price date {parsed_date} is in the future"
        )

    # 8. raw price must be below the implausibility ceiling
    if price >= _MAX_PRICE_RAW:
        return False, (
            f"Price {price:,.2f} {currency} exceeds the maximum plausible value "
            f"of {_MAX_PRICE_RAW:,.0f} — likely a data-entry error"
        )

    # 9. price per kg in GHS must be below the implausibility ceiling.
    #    Skip this check when the unit factor is None (crop-specific units
    #    such as 'Bunch' or 'Mudu' that require manual mapping).
    unit_key = str(raw_unit).strip().lower()
    factor = UNIT_MAP.get(unit_key)
    if factor is not None and factor > 0:
        price_ghs = price if currency == "GHS" else price * USD_TO_GHS_RATE
        price_per_kg = price_ghs / factor
        if price_per_kg >= _MAX_PRICE_PER_KG_GHS:
            return False, (
                f"Implied price per kg is GHS {price_per_kg:,.2f}, which exceeds "
                f"{_MAX_PRICE_PER_KG_GHS:,.0f} — check whether unit '{raw_unit}' "
                f"is correct for this row (price={price} {currency})"
            )

    return True, None


def validate_batch(
    rows: list[dict],
    source: str,
) -> tuple[list[dict], list[dict]]:
    """Validate a list of raw price rows.

    Parameters
    ----------
    rows:
        List of row dicts as returned by ``json.loads(df.to_json(orient='records'))``.
    source:
        Data source identifier forwarded to :func:`validate_row`.

    Returns
    -------
    clean_rows:
        Rows that passed every check, unchanged.
    rejected_rows:
        Rows that failed at least one check, with ``'_rejection_reason'`` added.
    """
    clean: list[dict] = []
    rejected: list[dict] = []

    for row in rows:
        is_valid, reason = validate_row(row, source)
        if is_valid:
            clean.append(row)
        else:
            rejected.append({**row, "_rejection_reason": reason})

    logger.info(
        "Validation complete [source=%s]: %d clean, %d rejected (%.1f%% pass rate)",
        source,
        len(clean),
        len(rejected),
        100 * len(clean) / len(rows) if rows else 0.0,
    )
    if rejected:
        # Log a sample of reasons to help spot systematic issues quickly
        sample = [r["_rejection_reason"] for r in rejected[:5]]
        logger.debug("First rejection reasons: %s", sample)

    return clean, rejected
