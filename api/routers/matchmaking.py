from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from api.dependencies import get_matcher, get_recommender
from models.crop_recommender import CropRecommender
from models.matchmaking_engine import MatchmakingEngine

router = APIRouter()


@router.get("/api/match/{crop}")
def match_listings(
    crop: Annotated[str, Path(max_length=60)],
    buyer_district_id: Annotated[int, Query(gt=0)],
    quantity_kg: Annotated[float, Query(gt=0, le=500_000)] = 1000.0,
    max_distance_km: Optional[float] = None,
    max_price_ghs: Optional[float] = None,
    min_quantity_kg: Optional[float] = None,
    exclude_high_risk: bool = False,
    matcher: MatchmakingEngine = Depends(get_matcher),
):
    """Return ranked farmer listings for a buyer query, scored by match quality."""
    filters: dict = {}
    if max_distance_km is not None:
        filters["max_distance_km"] = max_distance_km
    if max_price_ghs is not None:
        filters["max_price_ghs"] = max_price_ghs
    if min_quantity_kg is not None:
        filters["min_quantity_kg"] = min_quantity_kg
    if exclude_high_risk:
        filters["exclude_csi"] = True

    return matcher.search(crop, buyer_district_id, quantity_kg, filters=filters)


@router.get("/api/market/{crop}")
def market_overview(
    crop: Annotated[str, Path(max_length=60)],
    matcher: MatchmakingEngine = Depends(get_matcher),
):
    """Return market-level supply, price, and risk summary for a crop."""
    return matcher.get_market_overview(crop)


@router.get("/api/recommend/farmer/{farmer_id}")
def recommend_for_farmer(
    farmer_id: Annotated[int, Path(gt=0)],
    recommender: CropRecommender = Depends(get_recommender),
):
    """Return personalised crop recommendations for a registered farmer."""
    result = recommender.recommend_for_declaration(farmer_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Farmer {farmer_id} not found or has no district assigned",
        )
    return result


@router.get("/api/recommend/{district_id}")
def recommend_for_district(
    district_id: Annotated[int, Path(gt=0)],
    recommender: CropRecommender = Depends(get_recommender),
):
    """Return top-5 crop recommendations for a district."""
    results = recommender.recommend(district_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendations available for district {district_id}",
        )
    return {"district_id": district_id, "recommendations": results}
