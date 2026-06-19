"""
Byproduct marketplace for AgriMatch (M16).

Search, rank, and match buyers to active byproduct listings.
Byproducts are priced by negotiation; landed_cost shows
only the transport component.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from db.connection import get_session
from db.repositories.byproduct_repo import ByproductRepo
from utils.math_utils import safe_float as _f

logger = logging.getLogger(__name__)

_URGENCY_ORDER = {"urgent": 0, "perishable": 1, "stable": 2}


def _urgency(is_perishable: bool, available_date: date) -> str:
    days_to = (available_date - date.today()).days
    if is_perishable and days_to <= 3:
        return "urgent"
    if is_perishable:
        return "perishable"
    return "stable"


class ByproductMarketplace:

    def __init__(self):
        self._logistics = None  # injected at startup via app.state

    # ── Method 1: search ─────────────────────────────────────────────────────

    def search(
        self,
        byproduct_type: str,
        buyer_district_id: Optional[int] = None,
        quantity_kg_needed: Optional[float] = None,
        max_results: int = 20,
    ) -> dict:
        """Return ranked byproduct listings for a buyer query."""
        today     = date.today()
        window_to = today + timedelta(days=90)

        with get_session() as db:
            if buyer_district_id is not None:
                rows = ByproductRepo.search_with_distance(
                    db, byproduct_type, buyer_district_id, today, window_to
                )
            else:
                rows = ByproductRepo.search_without_buyer(
                    db, byproduct_type, today, window_to
                )

        results = []
        for row in rows:
            qty      = float(row.estimated_quantity_kg)
            farm_did = int(row.district_id)
            cargo    = quantity_kg_needed if quantity_kg_needed else qty

            if buyer_district_id is None:
                distance_km        = None
                delivery_cost      = None
                landed_cost_per_kg = None
            elif farm_did == buyer_district_id:
                distance_km        = 0.0
                delivery_cost      = 0.0
                landed_cost_per_kg = 0.0
            else:
                distance_km = round(_f(row.road_distance_km), 1)
                logi = (
                    self._logistics.get_delivery_cost(farm_did, buyer_district_id, cargo)
                    if self._logistics else None
                )
                delivery_cost      = round(_f(logi["total_cost_ghs"]), 2) if logi else 0.0
                landed_cost_per_kg = round(delivery_cost / qty, 4) if qty > 0 else 0.0

            urgency    = _urgency(bool(row.is_perishable), row.available_date)
            first_name = str(row.farmer_name).split()[0] if row.farmer_name else "Unknown"

            results.append({
                "byproduct_declaration_id": int(row.byproduct_id),
                "primary_declaration_id":   int(row.declaration_id),
                "crop":                     str(row.crop),
                "byproduct_type":           str(row.byproduct_type),
                "estimated_quantity_kg":    qty,
                "is_perishable":            bool(row.is_perishable),
                "available_date":           str(row.available_date),
                "district":                 str(row.district_name),
                "region":                   str(row.region_name),
                "distance_km":              distance_km,
                "delivery_cost_ghs":        delivery_cost,
                "landed_cost_per_kg":       landed_cost_per_kg,
                "perishability_urgency":    urgency,
                "farmer_name":              first_name,
            })

        results.sort(key=lambda r: (
            _URGENCY_ORDER.get(r["perishability_urgency"], 2),
            r["distance_km"] if r["distance_km"] is not None else 0.0,
            -r["estimated_quantity_kg"],
        ))

        return {
            "byproduct_type":    byproduct_type,
            "buyer_district_id": buyer_district_id,
            "total_found":       len(results),
            "results":           results[:max_results],
        }

    # ── Method 2: get_all_byproduct_types ────────────────────────────────────

    def get_all_byproduct_types(self) -> list:
        """Return market-level summary of all active byproduct types."""
        today     = date.today()
        window_to = today + timedelta(days=90)

        with get_session() as db:
            rows = ByproductRepo.get_all_byproduct_types(db, today, window_to)

        return [
            {
                "byproduct_type":         str(r.byproduct_type),
                "total_listings":         int(r.total_listings),
                "total_kg_available":     float(r.total_kg),
                "is_perishable":          bool(r.is_perishable),
                "nearest_available_date": str(r.nearest_date) if r.nearest_date else None,
                "regions_available":      sorted(r.regions) if r.regions else [],
            }
            for r in rows
        ]

    # ── Method 3: get_farmer_byproducts ──────────────────────────────────────

    def get_farmer_byproducts(self, farmer_id: int) -> dict:
        """Return all byproduct listings linked to a farmer's active declarations."""
        with get_session() as db:
            rows = ByproductRepo.get_farmer_byproducts(db, farmer_id)

        byproducts = []
        for r in rows:
            urgency = _urgency(bool(r.is_perishable), r.available_date)
            byproducts.append({
                "byproduct_declaration_id": int(r.id),
                "primary_declaration_id":   int(r.declaration_id),
                "byproduct_type":           str(r.byproduct_type),
                "crop":                     str(r.crop),
                "estimated_quantity_kg":    float(r.estimated_quantity_kg),
                "is_perishable":            bool(r.is_perishable),
                "available_date":           str(r.available_date),
                "status":                   str(r.status),
                "district":                 str(r.district_name),
                "region":                   str(r.region_name),
                "perishability_urgency":    urgency,
            })

        return {
            "farmer_id":      farmer_id,
            "total_listings": len(byproducts),
            "byproducts":     byproducts,
        }
