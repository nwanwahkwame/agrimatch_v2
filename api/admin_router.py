"""
Admin read + write endpoints.
Exposes real rows from: ghana_markets, ghana_districts, crop_reference, farmers.
All routes require the internal API secret (set via INTERNAL_API_SECRET env var).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.schemas.admin import (
    AdminFarmerItem,
    AdminMarketItem,
    CropItem,
    DistrictItem,
    FarmerStatusResponse,
    ModelAccuracyItem,
    PipelineStatsResponse,
    RegionItem,
    StatsResponse,
)
from api.security import require_internal
from api.services.admin_service import AdminService
from db.connection import get_session
from db.repositories.admin_repo import AdminRepo

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_internal)],
)


# ── Farmers ───────────────────────────────────────────────────────────────────

@router.get("/farmers", response_model=list[AdminFarmerItem])
def list_farmers():
    """All registered farmers joined with their district and declaration count."""
    with get_session() as db:
        rows = AdminRepo.list_farmers(db)
    return [
        {
            "id":           r.id,
            "name":         r.full_name,
            "phone":        r.phone_number,
            "district":     r.district_name  or "Unknown",
            "region":       r.region_name    or "Unknown",
            "declarations": int(r.declaration_count or 0),
            "status":       "active" if r.is_active else "declined",
            "joined":       r.created_at.date().isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class FarmerStatusBody(BaseModel):
    action: str   # "approve" | "decline"


@router.put("/farmers/{farmer_id}/status", response_model=FarmerStatusResponse)
def update_farmer_status(farmer_id: int, body: FarmerStatusBody):
    """Approve (is_active=true) or decline (is_active=false) a farmer."""
    if body.action not in ("approve", "decline"):
        raise HTTPException(400, "action must be 'approve' or 'decline'")
    is_active = body.action == "approve"
    with get_session() as db:
        rowcount = AdminRepo.update_farmer_status(db, farmer_id, is_active)
    if rowcount == 0:
        raise HTTPException(404, "Farmer not found")
    return {"id": farmer_id, "is_active": is_active, "action": body.action}


# ── Markets ───────────────────────────────────────────────────────────────────

@router.get("/markets", response_model=list[AdminMarketItem])
def list_markets():
    """All markets from ghana_markets, enriched with district name and latest price date."""
    with get_session() as db:
        rows = AdminRepo.list_markets(db)
    return [
        {
            "id":            r.id,
            "name":          r.market_name,
            "canonical":     r.canonical_name,
            "region":        r.region        or "Unknown",
            "district":      r.district_name or "Unknown",
            "is_major_hub":  bool(r.is_major_hub),
            "crops_tracked": int(r.crop_count or 0),
            "last_updated":  r.last_price_date.isoformat() if r.last_price_date else None,
            "status":        AdminService.get_market_status(r.last_price_date),
        }
        for r in rows
    ]


# ── Districts ─────────────────────────────────────────────────────────────────

@router.get("/districts", response_model=list[DistrictItem])
def list_districts():
    """All districts with region grouping, ordered by region then name."""
    with get_session() as db:
        rows = AdminRepo.list_districts(db)
    return [
        {
            "id":       r.id,
            "district": r.district_name,
            "region":   r.region_name,
            "lat":      float(r.centroid_lat) if r.centroid_lat else None,
            "lon":      float(r.centroid_lon) if r.centroid_lon else None,
        }
        for r in rows
    ]


# ── Crops ─────────────────────────────────────────────────────────────────────

@router.get("/crops", response_model=list[CropItem])
def list_crops():
    """All crop types from crop_reference table."""
    with get_session() as db:
        rows = AdminRepo.list_crops(db)
    return [
        {
            "id":                  r.id,
            "name":                r.internal_name,
            "unit":                r.default_unit,
            "is_byproduct_source": bool(r.is_byproduct_source),
            "byproduct_types":     r.byproduct_types or [],
        }
        for r in rows
    ]


# ── Summary stats ─────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
def summary_stats():
    """Live counts: active farmers, markets, declarations, total forecast value."""
    with get_session() as db:
        row = AdminRepo.get_stats(db)
    return {
        "active_farmers":      int(row.active_farmers      or 0),
        "total_markets":       int(row.total_markets       or 0),
        "active_declarations": int(row.active_declarations or 0),
        "total_value_ghs":     float(row.total_value_ghs   or 0),
    }


# ── Regions ───────────────────────────────────────────────────────────────────

@router.get("/regions", response_model=list[RegionItem])
def list_regions():
    """Regions with live market count and district count from DB."""
    with get_session() as db:
        rows = AdminRepo.list_regions(db)
    return [
        {
            "region":         r.region,
            "market_count":   int(r.market_count   or 0),
            "district_count": int(r.district_count or 0),
        }
        for r in rows
    ]


# ── Model accuracy ────────────────────────────────────────────────────────────

@router.get("/model-accuracy", response_model=list[ModelAccuracyItem])
def model_accuracy():
    """Per-market XGBoost and LSTM accuracy derived from model_baselines."""
    with get_session() as db:
        return AdminService.get_model_accuracy(db)


# ── Pipeline / ingestion stats ────────────────────────────────────────────────

@router.get("/pipeline/stats", response_model=PipelineStatsResponse)
def pipeline_stats():
    """Live row counts and last-run timestamps for every major table."""
    with get_session() as db:
        counts, last_run = AdminRepo.get_pipeline_stats(db)
    return {
        "row_counts":  counts,
        "recent_runs": [
            {
                "source":           r.source,
                "run_at":           r.run_at.isoformat() if r.run_at else None,
                "rows_clean":       r.rows_clean,
                "rows_quarantined": r.rows_quarantined,
                "status":           r.status,
            }
            for r in last_run
        ],
    }
