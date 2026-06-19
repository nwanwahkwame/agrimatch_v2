from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from api.dependencies import get_delay_clf, get_lstm, get_xgb
from api.security import require_internal
from models.delay_classifier import HarvestDelayClassifier
from models.lstm_predictor import LSTMPredictor
from models.xgboost_predictor import XGBoostPredictor

router = APIRouter()


@router.get("/api/forecast/{crop}/{market}")
def get_forecast(
    crop:   Annotated[str, Path(max_length=60)],
    market: Annotated[str, Path(max_length=100)],
    xgb: XGBoostPredictor = Depends(get_xgb),
):
    """Return 30/60/90-day XGBoost price forecast for a single crop-market pair."""
    return xgb.predict(crop, market)


@router.get("/api/forecast/{crop}")
def get_all_forecasts(
    crop: str,
    xgb: XGBoostPredictor = Depends(get_xgb),
):
    """Return 30/60/90-day forecasts for all markets with a model for this crop."""
    results = xgb.get_all_forecasts(crop)
    if not results:
        raise HTTPException(status_code=404, detail=f"No forecast models found for crop '{crop}'")
    return results


@router.get("/api/forecast/lstm/{crop}/{market}")
def get_lstm_forecast(
    crop:   Annotated[str, Path(max_length=60)],
    market: Annotated[str, Path(max_length=100)],
    lstm: LSTMPredictor = Depends(get_lstm),
):
    """Return 30/60/90-day LSTM price forecast for a single crop-market pair."""
    return lstm.predict(crop, market)


@router.get("/api/delay/{district_id}")
def get_delay_prediction(
    district_id: int,
    clf: HarvestDelayClassifier = Depends(get_delay_clf),
):
    """Return harvest delay prediction for a district."""
    result = clf.predict_delay(district_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No climate data available for district {district_id}")
    return result


@router.post("/api/delay/update-declarations", dependencies=[Depends(require_internal)])
def update_declarations(clf: HarvestDelayClassifier = Depends(get_delay_clf)):
    """Run harvest delay update across all active farmer declarations."""
    return clf.update_all_active_declarations()
