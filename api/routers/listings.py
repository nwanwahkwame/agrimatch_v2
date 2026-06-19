import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from api.schemas.listings import ListingsResponse
from db.connection import get_session
from db.repositories.listings_repo import ListingsRepo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/farmers/{farmer_id}/profile")
def farmer_profile(farmer_id: Annotated[int, Path(gt=0)]):
    """Public profile for a farmer -- active listings and completed sales count."""
    with get_session() as db:
        info, listings, sales_count = ListingsRepo.get_farmer_profile(db, farmer_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Farmer not found")

    return {
        "farmer_id":       farmer_id,
        "full_name":       info.full_name,
        "district":        info.district_name,
        "region":          info.region_name,
        "member_since":    str(info.created_at.date()) if info.created_at else None,
        "completed_sales": sales_count,
        "active_listings": [
            {
                "id":                 l.id,
                "crop":               l.crop,
                "quantity_kg":        float(l.quantity_kg),
                "harvest_date":       str(l.harvest_date),
                "price_forecast_ghs": float(l.price_forecast_ghs) if l.price_forecast_ghs else None,
                "csi_flag":           l.csi_flag or "normal",
            }
            for l in listings
        ],
    }


def _listing_row(r) -> dict:
    return {
        "declaration_id":        r.declaration_id,
        "farmer_name":           r.farmer_name,
        "crop":                  r.crop,
        "quantity_kg":           float(r.quantity_kg or 0),
        "harvest_date":          str(r.harvest_date) if r.harvest_date else None,
        "price_forecast_ghs":    float(r.price_forecast_ghs) if r.price_forecast_ghs else None,
        "csi_flag":              r.csi_flag or "normal",
        "adjusted_harvest_date": str(r.adjusted_harvest_date) if r.adjusted_harvest_date else None,
        "district":              getattr(r, "district", None) or "Unknown",
        "region":                getattr(r, "region",   None) or "Unknown",
        "match_score":           None,  # not computed for unmatched browse endpoints
        "distance_km":           None,
        "delivery_cost_ghs":     None,
        "landed_cost_per_kg":    None,
    }


@router.get("/api/declarations/{declaration_id}")
def get_declaration(declaration_id: Annotated[int, Path(gt=0)]):
    """Single farmer declaration by ID -- used by the listing detail page."""
    with get_session() as db:
        row = ListingsRepo.get_by_id(db, declaration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Declaration not found")
    return {
        "id":                   row.id,
        "farmer_id":            row.farmer_id,
        "farmer_name":          row.farmer_name,
        "district_name":        row.district_name,
        "district_id":          row.district_id,
        "crop":                 row.crop,
        "quantity_kg":          float(row.quantity_kg or 0),
        "harvest_date":         str(row.harvest_date) if row.harvest_date else None,
        "adjusted_harvest_date": str(row.adjusted_harvest_date) if row.adjusted_harvest_date else None,
        "status":               row.status or "active",
        "price_forecast_ghs":   float(row.price_forecast_ghs) if row.price_forecast_ghs else None,
        "csi_flag":             row.csi_flag or "normal",
        "source":               row.source or "farmer_data_import",
    }


@router.get("/api/listings", response_model=ListingsResponse)
def all_listings(
    region: str = "",
    crop: str = "",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """All active declarations with optional region and/or crop filter."""
    with get_session() as db:
        rows = ListingsRepo.get_all_active(db, region=region, crop=crop, limit=limit)
    results = [{**_listing_row(r), "source": r.source or "farmer_data_import", "is_new": bool(r.is_new)} for r in rows]
    return {"total_found": len(rows), "results": results}


@router.get("/api/listings/fresh", response_model=ListingsResponse)
def fresh_listings(limit: Annotated[int, Query(ge=1, le=200)] = 40):
    """Upcoming harvests ordered soonest-first."""
    with get_session() as db:
        rows = ListingsRepo.get_fresh(db, limit=limit)
    results = [{**_listing_row(r), "is_new": bool(r.is_new)} for r in rows]
    return {"total_found": len(rows), "results": results}


@router.get("/api/listings/best", response_model=ListingsResponse)
def best_prices(limit: Annotated[int, Query(ge=1, le=100)] = 20):
    """Top active listings across all crops sorted by price forecast."""
    with get_session() as db:
        rows = ListingsRepo.get_best_prices(db, limit=limit)
    results = [_listing_row(r) for r in rows]
    return {"total_found": len(rows), "results": results}
