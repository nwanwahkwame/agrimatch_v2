import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_delay_clf, get_lstm, get_xgb
from db.connection import get_session
from db.repositories.reference_repo import ReferenceRepo
from models.delay_classifier import HarvestDelayClassifier
from models.lstm_predictor import LSTMPredictor
from models.xgboost_predictor import XGBoostPredictor
from utils.cache import TtlCache

router = APIRouter()
logger = logging.getLogger(__name__)

_cache = TtlCache(ttl=3600)


@router.get("/api/crops")
def public_crops():
    """Crop types from crop_reference -- used by homepage and shop filters."""
    def fetch():
        try:
            with get_session() as db:
                rows = ReferenceRepo.get_crops(db)
            return [
                {
                    "id":                  r.id,
                    "name":                r.internal_name,
                    "is_byproduct_source": bool(r.is_byproduct_source),
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to fetch crops")
            raise HTTPException(status_code=503, detail="Crop data temporarily unavailable")
    return _cache.get_or_set("crops", fetch)


@router.get("/api/regions")
def public_regions():
    """Regions with market and district counts -- used by homepage browse cards."""
    def fetch():
        try:
            with get_session() as db:
                rows = ReferenceRepo.get_regions(db)
            return [
                {
                    "region":         r.region,
                    "market_count":   int(r.market_count   or 0),
                    "district_count": int(r.district_count or 0),
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to fetch regions")
            raise HTTPException(status_code=503, detail="Region data temporarily unavailable")
    return _cache.get_or_set("regions", fetch)


@router.get("/api/stats")
def public_stats():
    """Aggregate counts for the animated homepage section."""
    def fetch():
        try:
            with get_session() as db:
                row = ReferenceRepo.get_stats(db)
            return {
                "active_farmers":      int(row.active_farmers      or 0),
                "total_markets":       int(row.total_markets       or 0),
                "active_declarations": int(row.active_declarations or 0),
                "total_value_ghs":     float(row.total_value_ghs   or 0),
            }
        except Exception:
            logger.exception("Failed to fetch stats")
            raise HTTPException(status_code=503, detail="Stats temporarily unavailable")
    return _cache.get_or_set("stats", fetch)


@router.get("/api/model-accuracy")
def public_model_accuracy():
    """Per-market model accuracy -- used on homepage AnimatedStats."""
    def fetch():
        try:
            with get_session() as db:
                rows = ReferenceRepo.get_model_accuracy(db)
            markets: dict = {}
            for r in rows:
                key = str(r.market)
                if key not in markets:
                    markets[key] = {"market": key}
                if r.model_type == "xgboost":
                    markets[key]["xgb"]           = float(r.accuracy_pct or 0)
                    markets[key]["xgb_mae"]       = float(r.mae or 0)
                    markets[key]["training_rows"] = int(r.training_rows or 0)
                elif r.model_type == "lstm":
                    markets[key]["lstm"] = float(r.accuracy_pct or 0)
            return list(markets.values())[:20]
        except Exception:
            logger.exception("Failed to fetch model accuracy")
            raise HTTPException(status_code=503, detail="Model accuracy data temporarily unavailable")
    return _cache.get_or_set("model_accuracy", fetch)


@router.get("/api/models/status")
def models_status(
    xgb:  XGBoostPredictor       = Depends(get_xgb),
    lstm: LSTMPredictor          = Depends(get_lstm),
    clf:  HarvestDelayClassifier = Depends(get_delay_clf),
):
    """Return loaded model counts and API health."""
    return {
        "xgboost_models":   len(xgb.models),
        "lstm_models":      len(lstm.models),
        "delay_classifier": clf.model is not None,
        "api_version":      "1.0.0",
        "last_updated":     datetime.now(timezone.utc).isoformat(),
    }
