"""
Ingestion pipeline tests.

Tests 1-6 are pure-Python unit tests — no database required.
Tests 7-8 use the in-memory SQLite database via the fixtures in conftest.py.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from config.crop_map import CROP_MAP
from config.unit_map import UNIT_MAP
from db.models import CleanPrice, PriceQuarantine, RawPrice
from ingestion.transformers import load_to_database, transform_batch_hdx
from ingestion.validators import validate_row


# ── Shared helpers ────────────────────────────────────────────────────────────

def _valid_row(**overrides) -> dict:
    """Return a minimal row dict that passes every validation check."""
    base = {
        "date":      str(date.today() - timedelta(days=30)),
        "market":    "Accra",
        "commodity": "Maize",
        "price":     5.0,
        "currency":  "GHS",
        "unit":      "kg",
    }
    return {**base, **overrides}


def _clean_row(raw_id: int, **overrides) -> dict:
    """Return a clean_prices-compatible dict for use with load_to_database."""
    base = {
        "raw_id":      raw_id,
        "market":      "Accra",
        "region":      "Greater Accra",
        "district_id": None,
        "crop":        "maize",
        "unit":        "kg",
        "price_ghs":   Decimal("5.00"),
        "price_date":  date(2024, 1, 15),
        "source":      "hdx",
    }
    return {**base, **overrides}


def _insert_raw(session, payload: dict | None = None) -> int:
    """Insert one RawPrice and return its DB-assigned id."""
    raw = RawPrice(
        source="hdx",
        raw_payload=payload or {"test": True},
        file_ref="test.csv",
    )
    session.add(raw)
    session.flush()     # populates .id without committing
    return raw.id


# ── 1. test_crop_map_coverage ─────────────────────────────────────────────────

def test_crop_map_coverage():
    cases = [
        # HDX names (exact strings from the WFP Ghana dataset)
        ("maize (white)",    "maize"),
        ("maize (yellow)",   "maize"),
        ("tomatoes",         "tomato"),
        ("onions (local)",   "onion"),
        ("onions",           "onion"),
        ("cassava",          "cassava"),
        ("yam",              "yam"),
        ("sorghum",          "sorghum"),
        ("millet",           "millet"),
        # MoFA-style common variants
        ("rice (milled)",    "rice"),
        ("groundnuts",       "groundnut"),
        ("cowpea",           "cowpea"),
    ]
    for raw, expected in cases:
        result = CROP_MAP.get(raw)
        assert result == expected, (
            f"CROP_MAP[{raw!r}] should be {expected!r}, got {result!r}"
        )


# ── 2. test_unit_conversion ───────────────────────────────────────────────────

def test_unit_conversion():
    # 100 kg bag: 5000 GHS / 100 kg = 50 GHS/kg
    factor_100 = UNIT_MAP.get("100 kg")
    assert factor_100 == 100.0, f"Expected 100.0, got {factor_100}"
    assert 5000 / factor_100 == pytest.approx(50.0)

    # 50 kg bag: 2500 GHS / 50 kg = 50 GHS/kg
    factor_50 = UNIT_MAP.get("50 kg")
    assert factor_50 == 50.0, f"Expected 50.0, got {factor_50}"
    assert 2500 / factor_50 == pytest.approx(50.0)

    # 1 kg (already per-kg): factor must be 1.0
    assert UNIT_MAP.get("kg") == 1.0

    # Crop-specific unit (bunch) must resolve to None → quarantine path
    assert UNIT_MAP.get("bunch") is None


# ── 3. test_validate_row_valid ────────────────────────────────────────────────

def test_validate_row_valid():
    ok, reason = validate_row(_valid_row(), source="hdx")
    assert ok is True
    assert reason is None


# ── 4. test_validate_row_negative_price ──────────────────────────────────────

def test_validate_row_negative_price():
    ok, reason = validate_row(_valid_row(price=-5.0), source="hdx")
    assert ok is False
    assert reason is not None
    assert "greater than zero" in reason


# ── 5. test_validate_row_future_date ─────────────────────────────────────────

def test_validate_row_future_date():
    tomorrow = str(date.today() + timedelta(days=1))
    ok, reason = validate_row(_valid_row(date=tomorrow), source="hdx")
    assert ok is False
    assert reason is not None
    assert "future" in reason.lower()


# ── 6. test_validate_row_missing_market ──────────────────────────────────────

def test_validate_row_missing_market():
    ok, reason = validate_row(_valid_row(market=""), source="hdx")
    assert ok is False
    assert reason is not None
    assert "market" in reason.lower()


# ── 7. test_duplicate_detection ──────────────────────────────────────────────

def test_duplicate_detection(db_session, patch_get_session):
    raw_id = _insert_raw(db_session)
    row = _clean_row(raw_id)

    # First load — row is new, should be inserted
    s1 = load_to_database([row.copy()], [], source="hdx", rows_fetched=1)
    assert s1["rows_clean"] == 1
    assert s1["rows_duplicate"] == 0
    assert db_session.query(CleanPrice).count() == 1

    # Second load — same (market, crop, unit, price_date, source) key
    s2 = load_to_database([row.copy()], [], source="hdx", rows_fetched=1)
    assert s2["rows_clean"] == 0
    assert s2["rows_duplicate"] == 1

    # Still only one row — no double-insert
    assert db_session.query(CleanPrice).count() == 1


# ── 8. test_quarantine_on_bad_row ────────────────────────────────────────────

def test_quarantine_on_bad_row(db_session, patch_get_session):
    raw_id = _insert_raw(db_session, payload={"commodity": "UNKNOWN_CROP_XYZ"})

    bad_row = {
        "commodity": "UNKNOWN_CROP_XYZ",   # not in CROP_MAP
        "unit":      "kg",
        "price":     5.0,
        "currency":  "GHS",
        "market":    "Accra",
        "date":      "2024-01-15",
    }

    # Transformer should reject the row with an unmapped_crop reason
    clean_rows, failed_rows = transform_batch_hdx([bad_row], [raw_id])
    assert clean_rows == []
    assert len(failed_rows) == 1
    assert failed_rows[0]["_transform_reason"].startswith("unmapped_crop")

    # Attach raw_id so load_to_database can write the quarantine FK
    failed_rows[0]["raw_id"] = raw_id

    summary = load_to_database([], failed_rows, source="hdx", rows_fetched=1)

    assert summary["rows_quarantined"] == 1
    assert summary["rows_clean"] == 0
    assert db_session.query(CleanPrice).count() == 0
    assert db_session.query(PriceQuarantine).count() == 1

    # Confirm the stored rejection reason
    q = db_session.query(PriceQuarantine).one()
    assert "UNKNOWN_CROP_XYZ" in q.rejection_reason
