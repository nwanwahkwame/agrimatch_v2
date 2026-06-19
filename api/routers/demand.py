from fastapi import APIRouter

from api.schemas.demand import BuyerRequestIn, CreateDemandResponse, DemandItem
from db.connection import get_session
from db.repositories.demand_repo import DemandRepo

router = APIRouter()


@router.post("/api/demand", status_code=201, response_model=CreateDemandResponse)
def post_demand(req: BuyerRequestIn):
    """Buyer posts a crop request to the demand board."""
    with get_session() as db:
        row = DemandRepo.create(
            db,
            crop=req.crop,
            quantity_kg=req.quantity_kg,
            region=req.region,
            target_date=req.target_date,
            buyer_name=req.buyer_name,
            buyer_phone=req.buyer_phone,
            notes=req.notes,
        )
    return {"id": int(row.id), "created_at": row.created_at.isoformat()}


@router.get("/api/demand", response_model=list[DemandItem])
def list_demand(crop: str = "", region: str = "", limit: int = 50):
    """Return open buyer requests, newest first."""
    limit = min(limit, 200)
    with get_session() as db:
        rows = DemandRepo.list_open(db, crop=crop, region=region, limit=limit)
    return [
        {
            "id":          int(r.id),
            "crop":        r.crop,
            "quantity_kg": float(r.quantity_kg),
            "region":      r.region or "",
            "target_date": str(r.target_date) if r.target_date else None,
            "buyer_name":  r.buyer_name,
            "notes":       r.notes or "",
            "status":      r.status,
            "created_at":  r.created_at.isoformat(),
        }
        for r in rows
    ]
