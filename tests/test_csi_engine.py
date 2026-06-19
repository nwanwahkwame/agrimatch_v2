"""
Tests for M6 CSIEngine.

Tests 1-3 and 5 use the in-memory SQLite database via conftest.py fixtures.
Test 4 (get_district_risk_summary) uses the live PostgreSQL database because
it requires the ghana_districts table and real climate_indicators data.
"""

from contextlib import contextmanager
from datetime import date, timedelta

import pytest

from db.models import ClimateIndicator, Farmer, FarmerDeclaration
from ingestion.csi_engine import CSIEngine


# ── Shared fixture helpers ────────────────────────────────────────────────────

TEST_DISTRICT_ID = 99  # arbitrary; SQLite ignores FK constraints


def _make_farmer(session) -> int:
    farmer = Farmer(
        full_name="Test Farmer",
        phone_number="0200000001",
        district_id=None,
        is_active=True,
    )
    session.add(farmer)
    session.flush()
    return farmer.id


def _make_declaration(session, farmer_id: int, crop: str, district_id: int,
                      harvest_date: date) -> int:
    decl = FarmerDeclaration(
        farmer_id=farmer_id,
        source="ussd",
        crop=crop,
        quantity_kg=500,
        district_id=district_id,
        harvest_date=harvest_date,
        status="active",
        csi_flag="normal",
    )
    session.add(decl)
    session.flush()
    return decl.id


def _make_climate(session, district_id: int, flag_level: str,
                  harvest_delay_days: int, csi_maize: float = 0.3,
                  indicator_date: date = None) -> None:
    if indicator_date is None:
        indicator_date = date.today()
    row = ClimateIndicator(
        district_id=district_id,
        indicator_date=indicator_date,
        spi_30day=0.5,
        et0_mm=4.2,
        csi_maize=csi_maize,
        csi_tomato=0.2,
        csi_onion=0.1,
        csi_cassava=0.15,
        csi_rice=0.25,
        csi_plantain=0.18,
        harvest_delay_days=harvest_delay_days,
        flag_level=flag_level,
    )
    session.add(row)
    session.flush()


@pytest.fixture
def patch_csi_session(db_session, monkeypatch):
    """Replace get_session in ingestion.csi_engine with the test SQLite session."""
    @contextmanager
    def _fake():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr("ingestion.csi_engine.get_session", _fake)


# ── Test 1: get_csi_for_declaration returns valid data ───────────────────────

def test_get_csi_for_declaration(db_session, patch_csi_session):
    farmer_id = _make_farmer(db_session)
    decl_id = _make_declaration(
        db_session, farmer_id, "maize", TEST_DISTRICT_ID,
        harvest_date=date.today() + timedelta(days=30),
    )
    _make_climate(db_session, TEST_DISTRICT_ID, flag_level="normal",
                  harvest_delay_days=0, csi_maize=0.35)
    db_session.commit()

    result = CSIEngine().get_csi_for_declaration(decl_id)

    assert result is not None
    assert isinstance(result["csi_value"], float)
    assert abs(result["csi_value"] - 0.35) < 0.001
    assert result["flag_level"] == "normal"
    assert result["harvest_delay_days"] == 0
    assert result["indicator_date"] == date.today()


# ── Test 2: update_declaration_csi updates csi_flag and adjusted_harvest_date

def test_update_declaration_csi(db_session, patch_csi_session):
    farmer_id = _make_farmer(db_session)
    harvest = date.today() + timedelta(days=45)
    decl_id = _make_declaration(
        db_session, farmer_id, "maize", TEST_DISTRICT_ID,
        harvest_date=harvest,
    )
    _make_climate(db_session, TEST_DISTRICT_ID, flag_level="watch",
                  harvest_delay_days=7, csi_maize=0.55)
    db_session.commit()

    result = CSIEngine().update_declaration_csi(decl_id)

    assert result["was_updated"] is True
    assert result["old_flag"] == "normal"
    assert result["new_flag"] == "watch"
    assert result["new_adjusted_date"] == harvest + timedelta(days=7)

    # verify the DB row was actually updated
    db_session.expire_all()
    updated = db_session.get(FarmerDeclaration, decl_id)
    assert updated.csi_flag == "watch"
    assert updated.adjusted_harvest_date == harvest + timedelta(days=7)


# ── Test 3: run_all_active processes only active declarations ─────────────────

def test_run_all_active(db_session, patch_csi_session):
    farmer_id = _make_farmer(db_session)
    harvest = date.today() + timedelta(days=60)

    active_ids = []
    for crop in ("maize", "tomato", "rice", "cassava"):
        did = _make_declaration(db_session, farmer_id, crop, TEST_DISTRICT_ID, harvest)
        active_ids.append(did)

    # one inactive declaration that should be skipped
    inactive = FarmerDeclaration(
        farmer_id=farmer_id,
        source="ussd",
        crop="onion",
        quantity_kg=100,
        district_id=TEST_DISTRICT_ID,
        harvest_date=harvest,
        status="inactive",
        csi_flag="normal",
    )
    session = db_session
    session.add(inactive)

    _make_climate(db_session, TEST_DISTRICT_ID, flag_level="normal",
                  harvest_delay_days=0)
    db_session.commit()

    summary = CSIEngine().run_all_active()

    assert summary["total_processed"] == 4
    assert isinstance(summary["flag_changed"], int)
    assert isinstance(summary["date_adjusted"], int)
    assert isinstance(summary["moved_to_alert"], int)


# ── Test 4: get_district_risk_summary returns data for all 16 regions ─────────

def test_get_district_risk_summary():
    """Uses live PostgreSQL DB -- requires climate_indicators and ghana_districts."""
    from dotenv import load_dotenv
    load_dotenv(".env")

    summary = CSIEngine().get_district_risk_summary()

    assert isinstance(summary, list), "expected a list"
    assert len(summary) > 0, "no rows returned from climate_indicators"

    regions = {r["region"] for r in summary}
    assert len(regions) == 16, (
        f"expected 16 Ghana regions, got {len(regions)}: {sorted(regions)}"
    )
    for row in summary:
        assert row["flag_level"] in ("normal", "watch", "warning", "critical"), (
            f"unexpected flag_level: {row['flag_level']}"
        )
        assert row["as_of"] is not None


# ── Test 5: check_and_alert returns None for normal-flag declarations ──────────

def test_check_and_alert_returns_none_for_normal(db_session, patch_csi_session):
    farmer_id = _make_farmer(db_session)
    decl_id = _make_declaration(
        db_session, farmer_id, "maize", TEST_DISTRICT_ID,
        harvest_date=date.today() + timedelta(days=30),
    )
    _make_climate(db_session, TEST_DISTRICT_ID, flag_level="normal",
                  harvest_delay_days=0, csi_maize=0.1)
    db_session.commit()

    alert = CSIEngine().check_and_alert(decl_id)

    assert alert is None
