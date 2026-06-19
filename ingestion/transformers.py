"""
Transforms validated raw rows into the unified clean_prices schema.

Each public function returns a (result, error) tuple:
  - On success: (dict, None)  — dict matches clean_prices columns
  - On failure: (None, str)   — str is a short machine-readable reason

A failed row is never allowed to raise; all exceptions are caught and turned
into failure reasons so a single bad row cannot crash the whole batch.
"""

import logging
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd

from sqlalchemy import insert, select

from config.crop_map import CROP_MAP
from config.market_map import MARKET_MAP
from config.settings import USD_TO_GHS_RATE
from config.unit_map import UNIT_MAP
from db.connection import get_session
from db.models import CleanPrice, IngestionLog, PriceQuarantine

logger = logging.getLogger(__name__)

# Region string used when a market name has no entry in MARKET_MAP
_UNVERIFIED_REGION = "unverified_market"

# ── Crop-specific unit factors ────────────────────────────────────────────────
# UNIT_MAP is intentionally crop-agnostic (e.g. a "Bunch" for plantain weighs
# differently from a "Bunch" for bananas).  When UNIT_MAP returns None, the
# transformer falls back to this dict keyed by (canonical_crop, unit_lower).
#
# Value is (factor, output_unit):
#   factor      – divide the raw price by this to get price per output_unit
#   output_unit – the unit string written to clean_prices.unit
#
# Sources for weight estimates:
#   Plantain bunch : WFP/FEWSNET Ghana field guides (~12 kg average)
#   Yam 100 tubers : FAO Ghana SRID surveys (~1.5 kg/tuber puna yam)
#   Eggs 30 pcs    : no kg conversion; stored as price per tray (factor=1)
_CROP_UNIT_FACTORS: dict[tuple[str, str], tuple[float, str]] = {
    ("plantain", "bunch"):      (12.0,  "kg"),    # 12 kg/bunch
    ("yam",      "100 tubers"): (150.0, "kg"),    # 1.5 kg * 100
    ("eggs",     "30 pcs"):     (1.0,   "tray"),  # price already per tray
}

# ── MoFA column detection config ──────────────────────────────────────────────

# Keywords used to identify each logical column role from MoFA header names.
# The first column whose lowercased name contains any listed keyword wins.
_MOFA_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "market":    ["market"],
    "commodity": ["commodity", "crop", "product"],
    "unit":      ["unit"],
    "price":     ["price", "ghs", "cedis"],
    "date":      ["date", "week", "period"],
}

# 0-based positional fallback used when keyword detection finds nothing.
# These match the most common column order in MoFA SRID sheets.
_MOFA_POSITIONAL_FALLBACK: dict[str, int] = {
    "market":    0,
    "commodity": 1,
    "unit":      2,
    "price":     3,
    "date":      4,
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_date(value: Any) -> date | None:
    """Return a ``date`` from *value*, handling strings and ms timestamps."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    # pandas to_json() serialises datetime64 columns as ms-since-epoch integers
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.utcfromtimestamp(float(value) / 1000).date()
        except (ValueError, OSError):
            return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _to_ghs(price: float, currency: str) -> float:
    """Convert *price* to GHS using the configured USD_TO_GHS_RATE."""
    if currency.upper() == "GHS":
        return price
    return price * USD_TO_GHS_RATE


def _round_ghs(value: float) -> Decimal:
    """Round to 2 d.p. using ROUND_HALF_UP, matching Numeric(10,2) in the DB."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_mofa_date(value: Any) -> date | None:
    """Try DD/MM/YYYY (MoFA convention) first, then fall back to _parse_date.

    MoFA SRID files use DD/MM/YYYY in text columns and occasionally ISO strings
    or Excel serial numbers (handled by _parse_date's ms-timestamp branch).
    """
    if value is None:
        return None
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            pass
    return _parse_date(value)


# ── Single-row transformer ────────────────────────────────────────────────────

def transform_hdx_row(
    row_dict: dict,
    raw_id: int,
) -> tuple[dict | None, str | None]:
    """Transform one validated HDX row into a clean_prices-compatible dict.

    Parameters
    ----------
    row_dict:
        A single row dict produced by ``json.loads(df.to_json(orient='records'))``.
    raw_id:
        The ``id`` of the corresponding ``RawPrice`` record, used as the FK.

    Returns
    -------
    (clean_dict, None)
        Transformation succeeded; ``clean_dict`` matches the ``clean_prices`` columns.
    (None, reason)
        Transformation failed; ``reason`` is a short string such as
        ``'unmapped_crop: Wheat'`` or ``'unparseable_date: 01/01/2020'``.
    """
    try:
        # ── 1. Crop mapping ───────────────────────────────────────────────────
        raw_commodity = str(row_dict.get("commodity") or "").strip()
        internal_crop = CROP_MAP.get(raw_commodity.lower())
        if internal_crop is None:
            return None, f"unmapped_crop: {raw_commodity}"

        # ── 2. Unit mapping ───────────────────────────────────────────────────
        raw_unit = str(row_dict.get("unit") or "").strip()
        factor = UNIT_MAP.get(raw_unit.lower())
        output_unit = "kg"   # overridden below for crop-specific units

        if factor is None:
            crop_specific = _CROP_UNIT_FACTORS.get((internal_crop, raw_unit.lower()))
            if crop_specific is not None:
                factor, output_unit = crop_specific
            else:
                return None, f"unmapped_unit: {raw_unit}"

        # ── 3. Price → per output_unit ────────────────────────────────────────
        raw_price = row_dict.get("price")
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None, f"unparseable_price: {raw_price}"
        price_per_unit = price / factor   # e.g. 250 GHS / 50 kg = 5 GHS/kg

        # ── 4. Currency conversion → GHS ──────────────────────────────────────
        raw_currency = str(row_dict.get("currency") or "").strip().upper()
        price_ghs_per_kg = _to_ghs(price_per_unit, raw_currency)
        price_ghs_rounded = _round_ghs(price_ghs_per_kg)

        # ── 5. Market mapping ─────────────────────────────────────────────────
        raw_market = str(row_dict.get("market") or "").strip()
        market_entry = MARKET_MAP.get(raw_market.lower())
        if market_entry:
            canonical_market = market_entry["canonical_name"]
            region = market_entry["region"]
        else:
            # Unknown market: pass through with a sentinel region so analysts
            # can spot and add it to MARKET_MAP later.
            canonical_market = raw_market
            region = _UNVERIFIED_REGION
            logger.warning(
                "Market '%s' not in MARKET_MAP — stored as unverified (raw_id=%s)",
                raw_market,
                raw_id,
            )

        # ── 6. Date parsing ───────────────────────────────────────────────────
        raw_date = row_dict.get("date")
        price_date = _parse_date(raw_date)
        if price_date is None:
            return None, f"unparseable_date: {raw_date}"

        # ── 7. Build output dict ──────────────────────────────────────────────
        clean = {
            "raw_id":     raw_id,
            "market":     canonical_market,
            "region":     region,
            "district_id": None,          # not carried in HDX feed
            "crop":       internal_crop,
            "unit":       output_unit,
            "price_ghs":  price_ghs_rounded,
            "price_date": price_date,
            "source":     "hdx",
        }
        return clean, None

    except Exception as exc:  # noqa: BLE001
        # Catch-all: a transformer bug must never crash the batch.
        logger.exception("Unexpected error transforming raw_id=%s: %s", raw_id, exc)
        return None, f"unexpected_error: {exc}"


# ── Batch transformer ─────────────────────────────────────────────────────────

def transform_batch_hdx(
    rows: list[dict],
    raw_ids: list[int],
) -> tuple[list[dict], list[dict]]:
    """Transform a list of validated HDX rows.

    Parameters
    ----------
    rows:
        Validated row dicts (output of ``validate_batch`` clean list).
    raw_ids:
        Corresponding ``RawPrice.id`` values, one per row, in the same order.

    Returns
    -------
    clean_rows:
        Rows that transformed successfully; ready to bulk-insert into
        ``clean_prices``.
    failed_rows:
        Rows that could not be transformed.  Each dict is a copy of the
        original row with ``'_transform_reason'`` added.
    """
    if len(rows) != len(raw_ids):
        raise ValueError(
            f"rows ({len(rows)}) and raw_ids ({len(raw_ids)}) must be the same length"
        )

    clean: list[dict] = []
    failed: list[dict] = []

    for row, raw_id in zip(rows, raw_ids):
        result, reason = transform_hdx_row(row, raw_id)
        if result is not None:
            clean.append(result)
        else:
            failed.append({**row, "_transform_reason": reason})

    total = len(rows)
    logger.info(
        "Transform complete [source=hdx]: %d clean, %d failed (%.1f%% success rate)",
        len(clean),
        len(failed),
        100 * len(clean) / total if total else 0.0,
    )
    if failed:
        top = Counter(r["_transform_reason"] for r in failed).most_common(5)
        logger.debug("Top transform failure reasons: %s", top)

    return clean, failed


# ── MoFA column detection ─────────────────────────────────────────────────────

def detect_mofa_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """Return a mapping of logical role -> actual column name for a MoFA DataFrame.

    Each role is matched by scanning column names (case-insensitive) for
    the keywords defined in ``_MOFA_COLUMN_KEYWORDS``.  When no keyword match
    is found the function falls back to the positional index in
    ``_MOFA_POSITIONAL_FALLBACK`` and logs a warning so the caller knows the
    detection was uncertain.

    Parameters
    ----------
    df:
        A DataFrame produced by ``MoFAClient.parse_xlsx``.

    Returns
    -------
    dict mapping each role (``'market'``, ``'commodity'``, ``'unit'``,
    ``'price'``, ``'date'``) to an actual column name, or ``None`` if the
    DataFrame has too few columns for even a positional fallback.
    """
    cols: list[str] = [str(c) for c in df.columns]
    cols_lower: list[str] = [c.strip().lower() for c in cols]
    col_map: dict[str, str | None] = {}

    for role, keywords in _MOFA_COLUMN_KEYWORDS.items():
        matched: str | None = None
        for i, col_lower in enumerate(cols_lower):
            if any(kw in col_lower for kw in keywords):
                matched = cols[i]
                break

        if matched is not None:
            col_map[role] = matched
        else:
            fallback_idx = _MOFA_POSITIONAL_FALLBACK[role]
            if fallback_idx < len(cols):
                col_map[role] = cols[fallback_idx]
                logger.warning(
                    "detect_mofa_columns: no '%s' keyword match — "
                    "using positional fallback index %d ('%s'). Columns: %s",
                    role, fallback_idx, cols[fallback_idx], cols,
                )
            else:
                col_map[role] = None
                logger.warning(
                    "detect_mofa_columns: no '%s' keyword match and DataFrame "
                    "has only %d column(s) — role will produce empty values. Columns: %s",
                    role, len(cols), cols,
                )

    logger.debug("MoFA column map: %s", col_map)
    return col_map


# ── MoFA single-row transformer ───────────────────────────────────────────────

def transform_mofa_row(
    row_dict: dict,
    col_map: dict[str, str | None],
    raw_id: int,
) -> tuple[dict | None, str | None]:
    """Transform one validated MoFA row into a clean_prices-compatible dict.

    Parameters
    ----------
    row_dict:
        A single row dict from ``json.loads(df.to_json(orient='records'))``.
    col_map:
        Output of :func:`detect_mofa_columns` for this file's DataFrame.
    raw_id:
        The ``id`` of the corresponding ``RawPrice`` record.

    Returns
    -------
    (clean_dict, None)  on success; (None, reason) on failure.
    """
    try:
        def _get(role: str) -> str:
            col = col_map.get(role)
            return str(row_dict.get(col, "") if col else "").strip()

        # ── 1. Crop mapping ───────────────────────────────────────────────────
        raw_commodity = _get("commodity")
        internal_crop = CROP_MAP.get(raw_commodity.lower())
        if internal_crop is None:
            return None, f"unmapped_crop: {raw_commodity}"

        # ── 2. Unit mapping ───────────────────────────────────────────────────
        raw_unit = _get("unit")
        factor = UNIT_MAP.get(raw_unit.lower())
        output_unit = "kg"

        if factor is None:
            crop_specific = _CROP_UNIT_FACTORS.get((internal_crop, raw_unit.lower()))
            if crop_specific is not None:
                factor, output_unit = crop_specific
            else:
                return None, f"unmapped_unit: {raw_unit}"

        # ── 3. Price -> per output_unit (MoFA prices are always GHS) ─────────
        price_col = col_map.get("price")
        raw_price = row_dict.get(price_col) if price_col else None
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None, f"unparseable_price: {raw_price}"
        if price <= 0:
            return None, f"non_positive_price: {price}"
        price_ghs_rounded = _round_ghs(price / factor)

        # ── 4. Market mapping ─────────────────────────────────────────────────
        raw_market = _get("market")
        market_entry = MARKET_MAP.get(raw_market.lower())
        if market_entry:
            canonical_market = market_entry["canonical_name"]
            region = market_entry["region"]
        else:
            canonical_market = raw_market
            region = _UNVERIFIED_REGION
            logger.warning(
                "Market '%s' not in MARKET_MAP -- stored as unverified (raw_id=%s)",
                raw_market, raw_id,
            )

        # ── 5. Date parsing (DD/MM/YYYY first, then ISO / ms timestamp) ───────
        date_col = col_map.get("date")
        raw_date = row_dict.get(date_col) if date_col else None
        price_date = _parse_mofa_date(raw_date)
        if price_date is None:
            return None, f"unparseable_date: {raw_date}"

        # ── 6. Build output dict ──────────────────────────────────────────────
        return {
            "raw_id":      raw_id,
            "market":      canonical_market,
            "region":      region,
            "district_id": None,
            "crop":        internal_crop,
            "unit":        output_unit,
            "price_ghs":   price_ghs_rounded,
            "price_date":  price_date,
            "source":      "mofa_srid",
        }, None

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error transforming MoFA raw_id=%s: %s", raw_id, exc)
        return None, f"unexpected_error: {exc}"


# ── MoFA batch transformer ────────────────────────────────────────────────────

def transform_batch_mofa(
    rows: list[dict],
    raw_ids: list[int],
    col_map: dict[str, str | None],
) -> tuple[list[dict], list[dict]]:
    """Transform a list of validated MoFA rows.

    Parameters
    ----------
    rows:
        Validated row dicts (output of ``validate_batch`` clean list).
    raw_ids:
        Corresponding ``RawPrice.id`` values, one per row, in the same order.
    col_map:
        Output of :func:`detect_mofa_columns` for this file's DataFrame.

    Returns
    -------
    clean_rows, failed_rows
        Same contract as :func:`transform_batch_hdx`.
    """
    if len(rows) != len(raw_ids):
        raise ValueError(
            f"rows ({len(rows)}) and raw_ids ({len(raw_ids)}) must be the same length"
        )

    clean: list[dict] = []
    failed: list[dict] = []

    for row, raw_id in zip(rows, raw_ids):
        result, reason = transform_mofa_row(row, col_map, raw_id)
        if result is not None:
            clean.append(result)
        else:
            failed.append({**row, "_transform_reason": reason})

    total = len(rows)
    logger.info(
        "Transform complete [source=mofa_srid]: %d clean, %d failed (%.1f%% success rate)",
        len(clean),
        len(failed),
        100 * len(clean) / total if total else 0.0,
    )
    if failed:
        top = Counter(r["_transform_reason"] for r in failed).most_common(5)
        logger.debug("Top transform failure reasons: %s", top)

    return clean, failed


# ── Database loader ───────────────────────────────────────────────────────────

def load_to_database(
    clean_rows: list[dict],
    quarantine_rows: list[dict],
    source: str,
    rows_fetched: int,
) -> dict[str, Any]:
    """Persist transformed rows to ``clean_prices``, ``price_quarantine``, and
    ``ingestion_log`` in a single transaction.

    Duplicate detection
    -------------------
    Before inserting, the function queries ``clean_prices`` for rows that share
    the same ``(market, crop, unit, price_date, source)`` as any incoming clean
    row.  The query is scoped to the date range of the incoming batch to avoid
    a full table scan.  Duplicates are counted and skipped silently.

    Quarantine rows
    ---------------
    Each dict in *quarantine_rows* must carry a ``raw_id`` key (the FK into
    ``raw_prices``) and either a ``_rejection_reason`` or ``_transform_reason``
    key.  Rows missing ``raw_id`` cannot satisfy the NOT NULL constraint and are
    skipped with a warning; they are counted in ``rows_quarantine_skipped``.

    Error handling
    --------------
    If any unhandled exception occurs the main transaction is rolled back and a
    separate session writes a ``status='failed'`` row to ``ingestion_log`` so
    the failure is always recorded.

    Parameters
    ----------
    clean_rows:
        Output of :func:`transform_batch_hdx` (the clean list).
    quarantine_rows:
        Combined list of validation-rejected and transform-failed rows.
    source:
        Data source identifier, e.g. ``'hdx'`` or ``'mofa'``.
    rows_fetched:
        Total raw rows downloaded/read before any filtering.

    Returns
    -------
    A summary dict with keys: ``source``, ``rows_fetched``, ``rows_clean``,
    ``rows_duplicate``, ``rows_quarantined``, ``rows_quarantine_skipped``,
    ``status``, ``error``.
    """
    rows_clean_inserted = 0
    rows_duplicate = 0
    rows_quarantined_inserted = 0
    rows_quarantine_skipped = 0

    try:
        with get_session() as session:

            # ── 1. Duplicate detection ────────────────────────────────────────
            existing_keys: set[tuple] = set()
            if clean_rows:
                dates = [r["price_date"] for r in clean_rows if r.get("price_date")]
                if dates:
                    min_date, max_date = min(dates), max(dates)
                    existing = session.execute(
                        select(
                            CleanPrice.market,
                            CleanPrice.crop,
                            CleanPrice.unit,
                            CleanPrice.price_date,
                            CleanPrice.source,
                        ).where(
                            CleanPrice.source == source,
                            CleanPrice.price_date >= min_date,
                            CleanPrice.price_date <= max_date,
                        )
                    ).all()
                    existing_keys = {tuple(r) for r in existing}
                    if existing_keys:
                        logger.info(
                            "Found %d existing rows in date range %s → %s",
                            len(existing_keys), min_date, max_date,
                        )

            # ── 2. Filter duplicates ──────────────────────────────────────────
            new_rows: list[dict] = []
            for row in clean_rows:
                key = (
                    row["market"], row["crop"], row["unit"],
                    row["price_date"], row["source"],
                )
                if key in existing_keys:
                    rows_duplicate += 1
                else:
                    new_rows.append(row)

            if rows_duplicate:
                logger.info("Skipped %d duplicate rows", rows_duplicate)

            # ── 3. Bulk-insert clean rows ─────────────────────────────────────
            if new_rows:
                session.execute(
                    insert(CleanPrice),
                    [
                        {
                            "raw_id":      r["raw_id"],
                            "market":      r["market"],
                            "region":      r["region"],
                            "district_id": r.get("district_id"),
                            "crop":        r["crop"],
                            "unit":        r["unit"],
                            "price_ghs":   r["price_ghs"],
                            "price_date":  r["price_date"],
                            "source":      r["source"],
                        }
                        for r in new_rows
                    ],
                )
                rows_clean_inserted = len(new_rows)
                logger.info(
                    "Inserted %d clean rows into clean_prices", rows_clean_inserted
                )

            # ── 4. Bulk-insert quarantine rows ────────────────────────────────
            q_mappings: list[dict] = []
            for row in quarantine_rows:
                raw_id = row.get("raw_id") or row.get("_raw_id")
                if raw_id is None:
                    rows_quarantine_skipped += 1
                    logger.warning(
                        "Quarantine row has no raw_id — skipping DB insert "
                        "(reason=%s)",
                        row.get("_rejection_reason") or row.get("_transform_reason"),
                    )
                    continue
                reason = (
                    row.get("_rejection_reason")
                    or row.get("_transform_reason")
                    or "unknown"
                )
                payload = {k: v for k, v in row.items() if not k.startswith("_")}
                q_mappings.append(
                    {
                        "raw_id":           raw_id,
                        "rejection_reason": reason,
                        "raw_payload":      payload,
                    }
                )

            if q_mappings:
                session.execute(insert(PriceQuarantine), q_mappings)
                rows_quarantined_inserted = len(q_mappings)
                logger.info(
                    "Inserted %d rows into price_quarantine",
                    rows_quarantined_inserted,
                )

            # ── 5. Write ingestion log ────────────────────────────────────────
            session.add(
                IngestionLog(
                    source=source,
                    rows_fetched=rows_fetched,
                    rows_clean=rows_clean_inserted,
                    rows_quarantined=rows_quarantined_inserted,
                    status="success",
                )
            )
            # Commit happens on context manager exit.

        # ── 6. Zero-clean warning (after commit) ──────────────────────────────
        if rows_clean_inserted == 0 and rows_fetched > 0:
            print(
                "\n"
                "!! WARNING: Zero clean rows produced from "
                f"{rows_fetched:,} fetched rows [source={source}].\n"
                "   Check the quarantine table for rejection reasons.\n"
            )
            logger.warning(
                "Zero clean rows produced from %d fetched rows [source=%s]",
                rows_fetched, source,
            )

        summary: dict[str, Any] = {
            "source":                 source,
            "rows_fetched":           rows_fetched,
            "rows_clean":             rows_clean_inserted,
            "rows_duplicate":         rows_duplicate,
            "rows_quarantined":       rows_quarantined_inserted,
            "rows_quarantine_skipped": rows_quarantine_skipped,
            "status":                 "success",
            "error":                  None,
        }
        logger.info("Load complete: %s", summary)
        return summary

    except Exception as exc:
        logger.exception("load_to_database failed [source=%s]: %s", source, exc)

        # Record the failure in a fresh session — the original was rolled back.
        try:
            with get_session() as log_session:
                log_session.add(
                    IngestionLog(
                        source=source,
                        rows_fetched=rows_fetched,
                        rows_clean=0,
                        rows_quarantined=0,
                        status="failed",
                        error_detail=str(exc),
                    )
                )
        except Exception as log_exc:
            logger.error(
                "Could not write failure to ingestion_log: %s", log_exc
            )

        return {
            "source":                  source,
            "rows_fetched":            rows_fetched,
            "rows_clean":              0,
            "rows_duplicate":          0,
            "rows_quarantined":        0,
            "rows_quarantine_skipped": 0,
            "status":                  "failed",
            "error":                   str(exc),
        }
