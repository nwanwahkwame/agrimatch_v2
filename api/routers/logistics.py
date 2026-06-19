from typing import Optional

from fastapi import APIRouter, Depends

from api.dependencies import get_byproduct, get_coop
from api.security import require_internal
from models.byproduct_marketplace import ByproductMarketplace
from models.cooperative_logistics import CooperativeLogistics
from models.transport_matcher import match_pending_jobs

router = APIRouter()


@router.get("/api/logistics/groups")
def logistics_groups(
    save: bool = False,
    coop: CooperativeLogistics = Depends(get_coop),
):
    """Return cooperative truck-sharing groups for all active declarations."""
    groups = coop.find_groups()
    jobs_created = coop.save_groups(groups) if (save and groups) else 0
    return {
        "groups_found": len(groups),
        "jobs_created": jobs_created if save else None,
        "groups":       groups,
    }


@router.get("/api/logistics/farmer/{farmer_id}")
def logistics_for_farmer(
    farmer_id: int,
    coop: CooperativeLogistics = Depends(get_coop),
):
    """Return existing transport job memberships for a farmer's active declarations."""
    return coop.get_farmer_logistics_options(farmer_id)


@router.get("/api/byproducts")
def byproducts_overview(byproduct: ByproductMarketplace = Depends(get_byproduct)):
    """Summary of all active byproduct types for the marketplace homepage."""
    return byproduct.get_all_byproduct_types()


@router.get("/api/byproducts/farmer/{farmer_id}")
def farmer_byproducts(
    farmer_id: int,
    byproduct: ByproductMarketplace = Depends(get_byproduct),
):
    """All byproduct listings linked to a farmer's active declarations."""
    return byproduct.get_farmer_byproducts(farmer_id)


@router.get("/api/byproducts/{byproduct_type}")
def search_byproducts(
    byproduct_type: str,
    buyer_district_id: Optional[int] = None,
    quantity_kg: Optional[float] = None,
    byproduct: ByproductMarketplace = Depends(get_byproduct),
):
    """Ranked byproduct listings for a given type and optional buyer location."""
    return byproduct.search(byproduct_type, buyer_district_id, quantity_kg)


@router.post("/api/transport/match", dependencies=[Depends(require_internal)])
def run_transport_match():
    """Manually trigger transport provider matching for all pending jobs."""
    return match_pending_jobs()
