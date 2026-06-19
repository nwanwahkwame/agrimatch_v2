"""Unit tests for MatchmakingEngine scoring logic.

_compute_scores is a pure function with no DB calls, so no mocking is needed.
"""

from datetime import date, timedelta

import pytest

from models.matchmaking_engine import MatchmakingEngine, ScoringContext


def _scores(
    quantity_kg: float = 1000.0,
    quantity_kg_needed: float = 1000.0,
    district_id: int = 10,
    buyer_district_id: int = 10,
    road_km: float = 0.0,
    price: float = 10.0,
    median_price: float = 10.0,
    csi_flag: str = "normal",
    harvest_date=None,
    adjusted_harvest_date=None,
) -> dict:
    engine = MatchmakingEngine()
    hdate = harvest_date or (date.today() + timedelta(days=14))
    ctx = ScoringContext(
        declaration_id        = 1,
        district_id           = district_id,
        quantity_kg           = quantity_kg,
        harvest_date          = hdate,
        adjusted_harvest_date = adjusted_harvest_date,
        price_forecast_ghs    = price,
        csi_flag              = csi_flag,
        buyer_district_id     = buyer_district_id,
        quantity_kg_needed    = quantity_kg_needed,
        road_km               = road_km,
        median_price          = median_price,
    )
    return engine._compute_scores(ctx)


# ── Quantity score ────────────────────────────────────────────────────────────

def test_quantity_score_exact_match():
    assert _scores(quantity_kg=1000, quantity_kg_needed=1000)["quantity_score"] == 1.0


def test_quantity_score_surplus_caps_at_1():
    assert _scores(quantity_kg=5000, quantity_kg_needed=100)["quantity_score"] == 1.0


def test_quantity_score_partial():
    assert _scores(quantity_kg=500, quantity_kg_needed=1000)["quantity_score"] == pytest.approx(0.5)


def test_quantity_score_zero_needed_does_not_divide_by_zero():
    result = _scores(quantity_kg=1000, quantity_kg_needed=0)
    assert 0.0 <= result["quantity_score"] <= 1.0


# ── Distance score ────────────────────────────────────────────────────────────

def test_distance_score_same_district():
    assert _scores(district_id=10, buyer_district_id=10, road_km=0.0)["distance_score"] == 1.0


def test_distance_score_500km_is_zero():
    assert _scores(district_id=10, buyer_district_id=20, road_km=500.0)["distance_score"] == pytest.approx(0.0)


def test_distance_score_250km_is_half():
    assert _scores(district_id=10, buyer_district_id=20, road_km=250.0)["distance_score"] == pytest.approx(0.5)


def test_distance_score_clamped_above_500km():
    assert _scores(district_id=10, buyer_district_id=20, road_km=800.0)["distance_score"] == 0.0


# ── Price score ───────────────────────────────────────────────────────────────

def test_price_at_median_is_full():
    assert _scores(price=10.0, median_price=10.0)["price_score"] == pytest.approx(1.0)


def test_price_above_median_reduces_score():
    assert _scores(price=12.0, median_price=10.0)["price_score"] == pytest.approx(0.8)


def test_price_double_median_is_zero():
    assert _scores(price=20.0, median_price=10.0)["price_score"] == 0.0


def test_price_score_defaults_to_neutral_when_no_median():
    assert _scores(price=10.0, median_price=0.0)["price_score"] == pytest.approx(0.5)


# ── Reliability score ─────────────────────────────────────────────────────────

def test_reliability_normal_csi():
    assert _scores(csi_flag="normal")["reliability_score"] == pytest.approx(1.0)


def test_reliability_watch_csi():
    assert _scores(csi_flag="watch")["reliability_score"] == pytest.approx(0.9)


def test_reliability_warning_csi():
    assert _scores(csi_flag="warning")["reliability_score"] == pytest.approx(0.7)


def test_reliability_critical_csi():
    assert _scores(csi_flag="critical")["reliability_score"] == pytest.approx(0.4)


def test_reliability_adjusted_date_reduces_score():
    hdate = date.today() + timedelta(days=20)
    adj   = date.today() + timedelta(days=27)
    result = _scores(csi_flag="normal", harvest_date=hdate, adjusted_harvest_date=adj)
    assert result["reliability_score"] == pytest.approx(0.9)


def test_reliability_clamped_at_zero():
    hdate = date.today() + timedelta(days=20)
    adj   = date.today() + timedelta(days=27)
    # critical (-0.6) + adjusted (-0.1) = 0.3, but clamped to 0 if < 0
    result = _scores(csi_flag="critical", harvest_date=hdate, adjusted_harvest_date=adj)
    assert result["reliability_score"] >= 0.0


# ── Overall match score ───────────────────────────────────────────────────────

def test_match_score_in_unit_interval():
    result = _scores()
    assert 0.0 <= result["match_score"] <= 1.0


def test_match_score_keys_present():
    result = _scores()
    for key in ("match_score", "quantity_score", "distance_score",
                "price_score", "reliability_score", "timing_score", "distance_km"):
        assert key in result


def test_match_score_4_decimals():
    result = _scores()
    assert result["match_score"] == round(result["match_score"], 4)
