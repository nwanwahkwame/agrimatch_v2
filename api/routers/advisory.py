from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_logistics, get_xgb
from api.services.planting_service import PlantingService
from api.services.roi_service import RoiService
from models.xgboost_predictor import XGBoostPredictor

router = APIRouter()


@router.get("/api/planting/advisory")
def planting_advisory(district_id: Annotated[int, Query(gt=0)], crop: str = ""):
    """Return planting window advice for all crops (or one crop) in a district."""
    return PlantingService.get_advice(district_id, crop)


@router.get("/api/roi")
def roi_calculator(
    crop: str,
    quantity_kg: Annotated[float, Query(gt=0)],
    source_district_id: Annotated[int, Query(gt=0)],
    target_district_id: Annotated[int, Query(gt=0)],
    xgb:      XGBoostPredictor = Depends(get_xgb),
    logistics                  = Depends(get_logistics),
):
    """Estimate net return for selling a quantity of crop from source to target district."""
    return RoiService.calculate(
        crop, quantity_kg, source_district_id, target_district_id, xgb, logistics
    )
