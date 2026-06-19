from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_strategy
from models.strategy_generator import StrategyGenerator

router = APIRouter()


@router.get("/api/strategy/farmer/{farmer_id}")
def strategy_for_farmer(
    farmer_id: int,
    strategy: StrategyGenerator = Depends(get_strategy),
):
    """Return all sell and logistics strategy cards for a farmer's active declarations."""
    cards = strategy.generate_all_for_farmer(farmer_id)
    if not cards:
        raise HTTPException(
            status_code=404,
            detail=f"No active declarations found for farmer {farmer_id}",
        )
    return {"farmer_id": farmer_id, "strategies": cards}


@router.get("/api/strategy/buyer/{district_id}/{crop}")
def strategy_for_buyer(
    district_id: int,
    crop: str,
    quantity_kg: float = 1000.0,
    strategy: StrategyGenerator = Depends(get_strategy),
):
    """Return a buyer sourcing strategy for a crop in a given district."""
    result = strategy.buyer_sourcing_strategy(crop, district_id, quantity_kg)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast data available for {crop} near district {district_id}",
        )
    return result


@router.get("/api/strategy/logistics/{declaration_id}")
def strategy_logistics(
    declaration_id: int,
    strategy: StrategyGenerator = Depends(get_strategy),
):
    """Return a truck-sharing opportunity for a declaration, if one exists."""
    result = strategy.logistics_strategy(declaration_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No truck-sharing opportunity found for declaration {declaration_id}",
        )
    return result
