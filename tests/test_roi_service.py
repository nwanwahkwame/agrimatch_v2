"""Unit tests for RoiService.calculate."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from api.services.roi_service import RoiService


@contextmanager
def _fake_session(mock_db):
    yield mock_db


def _logistics(total_cost: float = 240.0, per_kg: float = 0.24):
    logi = MagicMock()
    logi.get_delivery_cost.return_value = {
        "total_cost_ghs":  total_cost,
        "cost_per_kg_ghs": per_kg,
    }
    return logi


def _xgb(last_price: float = 10.0, forecast: float = 12.0):
    xgb = MagicMock()
    xgb.predict.return_value = {
        "last_known_price": last_price,
        "forecasts":        [{"predicted_price_ghs": forecast}],
    }
    return xgb


@patch("api.services.roi_service.AdvisoryRepo.get_district_name")
@patch("api.services.roi_service.AdvisoryRepo.get_nearest_market")
@patch("api.services.roi_service.get_session")
def test_roi_uses_xgb_forecast_price(mock_gs, mock_market, mock_district):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_market.return_value = MagicMock(canonical_name="Kumasi")
    mock_district.return_value = MagicMock(district_name="Ejura")

    result = RoiService.calculate("maize", 1000.0, 10, 20, _xgb(forecast=12.0), _logistics(240.0, 0.24))

    assert result["forecast_price_per_kg"] == 12.0
    assert result["gross_revenue_ghs"]     == 12_000.0
    assert result["transport_cost_ghs"]    == 240.0
    assert result["net_revenue_ghs"]       == 11_760.0


@patch("api.services.roi_service.AdvisoryRepo.get_district_name")
@patch("api.services.roi_service.AdvisoryRepo.get_latest_price")
@patch("api.services.roi_service.AdvisoryRepo.get_nearest_market")
@patch("api.services.roi_service.get_session")
def test_roi_falls_back_to_db_price_when_no_xgb(mock_gs, mock_market, mock_latest, mock_district):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_market.return_value = MagicMock(canonical_name="Kumasi")
    mock_latest.return_value = MagicMock(price_ghs=8.0)
    mock_district.return_value = MagicMock(district_name="Ejura")

    xgb_no_model = MagicMock()
    xgb_no_model.predict.return_value = None

    result = RoiService.calculate("maize", 500.0, 10, 10, xgb_no_model, _logistics(0.0, 0.0))

    assert result["forecast_price_per_kg"] == 8.0
    assert result["gross_revenue_ghs"]     == 4_000.0
    assert result["net_revenue_ghs"]       == 4_000.0


@patch("api.services.roi_service.AdvisoryRepo.get_district_name")
@patch("api.services.roi_service.AdvisoryRepo.get_nearest_market")
@patch("api.services.roi_service.get_session")
def test_roi_margin_pct_calculation(mock_gs, mock_market, mock_district):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_market.return_value = MagicMock(canonical_name="Kumasi")
    mock_district.return_value = MagicMock(district_name="Ejura")

    # 1000 kg at GHS 10/kg = GHS 10000 gross, GHS 1000 transport -> GHS 9000 net
    result = RoiService.calculate("maize", 1000.0, 10, 20, _xgb(forecast=10.0), _logistics(1000.0, 1.0))

    assert result["margin_pct"] == round(9000 / 10000 * 100, 1)


@patch("api.services.roi_service.AdvisoryRepo.get_district_name")
@patch("api.services.roi_service.AdvisoryRepo.get_nearest_market")
@patch("api.services.roi_service.get_session")
def test_roi_response_keys_present(mock_gs, mock_market, mock_district):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_market.return_value = MagicMock(canonical_name="Kumasi")
    mock_district.return_value = MagicMock(district_name="Ejura")

    result = RoiService.calculate("maize", 100.0, 1, 2, _xgb(), _logistics())

    for key in ("crop", "quantity_kg", "source_district", "target_district",
                "forecast_price_per_kg", "gross_revenue_ghs",
                "transport_cost_ghs", "net_revenue_ghs", "margin_pct"):
        assert key in result
