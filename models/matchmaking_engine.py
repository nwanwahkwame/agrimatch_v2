"""
Matchmaking engine for AgriMatch (M14).

Ranks farmer declarations for a buyer query using five sub-scores:
quantity match, distance, price competitiveness, reliability, and timing.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from db.connection import get_session
from db.repositories.matchmaking_repo import MatchmakingRepo
from utils.math_utils import safe_float as _f

logger = logging.getLogger(__name__)

# ── Score weights ─────────────────────────────────────────────────────────────
_W_QUANTITY    = 0.25
_W_DISTANCE    = 0.25
_W_PRICE       = 0.20
_W_RELIABILITY = 0.20
_W_TIMING      = 0.10

# ── Distance normalisation ────────────────────────────────────────────────────
_DISTANCE_NORM_KM = 500.0   # distance at which distance_score reaches 0.0

# ── CSI reliability penalties ─────────────────────────────────────────────────
_RELIABILITY_PENALTY: dict[str, float] = {
    "watch":    0.1,
    "warning":  0.3,
    "critical": 0.6,
}
_DELAY_PENALTY = 0.1        # deducted when adjusted_harvest_date differs from harvest_date

# ── Timing score table (days_to_harvest → score) ─────────────────────────────
_TIMING_TABLE = [
    (7,   1.0),
    (14,  0.9),
    (30,  0.7),
    (60,  0.5),
]
_TIMING_FLOOR = 0.3

# ── Vehicle tiers for logistics cost lookup ───────────────────────────────────
_VEHICLE_CAPACITY_TIERS: list[tuple[float, str, list[int]]] = [
    (1500.0, "pickup",       [500, 1000, 1500]),
    (8000.0, "medium_truck", [2000, 5000, 8000]),
]
_VEHICLE_LARGE = ("large_truck", [8000, 15000, 20000])


def _vehicle_tier(qty_kg: float) -> tuple[str, int]:
    """Return (vehicle_type, closest_cargo_tier) for a requested quantity."""
    for cap, vtype, tiers in _VEHICLE_CAPACITY_TIERS:
        if qty_kg <= cap:
            return vtype, min(tiers, key=lambda t: abs(t - qty_kg))
    vtype, tiers = _VEHICLE_LARGE
    return vtype, min(tiers, key=lambda t: abs(t - qty_kg))


# ── Input contract for scoring ────────────────────────────────────────────────

@dataclass
class ScoringContext:
    declaration_id:        int
    district_id:           int
    quantity_kg:           float
    harvest_date:          Optional[date]
    adjusted_harvest_date: Optional[date]
    price_forecast_ghs:    Optional[float]
    csi_flag:              Optional[str]
    buyer_district_id:     int
    quantity_kg_needed:    float
    road_km:               float
    median_price:          float


class MatchmakingEngine:

    def __init__(self):
        self._logistics = None  # injected at startup via app.state

    # ── Pure scoring ─────────────────────────────────────────────────────────

    def _compute_scores(self, ctx: ScoringContext) -> dict:
        quantity_score = max(
            0.0,
            min(1.0, min(ctx.quantity_kg, ctx.quantity_kg_needed) / max(ctx.quantity_kg_needed, 1.0)),
        )

        if ctx.district_id == ctx.buyer_district_id:
            distance_score = 1.0
        else:
            distance_score = max(0.0, 1.0 - (ctx.road_km / _DISTANCE_NORM_KM))

        listing_price = _f(ctx.price_forecast_ghs)
        if ctx.median_price > 0 and listing_price > 0:
            price_score = max(0.0, 1.0 - ((listing_price - ctx.median_price) / ctx.median_price))
        else:
            price_score = 0.5

        reliability = 1.0
        reliability -= _RELIABILITY_PENALTY.get(ctx.csi_flag or "normal", 0.0)
        if ctx.adjusted_harvest_date and ctx.harvest_date and ctx.adjusted_harvest_date != ctx.harvest_date:
            reliability -= _DELAY_PENALTY
        reliability_score = max(0.0, reliability)

        effective = ctx.adjusted_harvest_date or ctx.harvest_date
        days_to   = (effective - date.today()).days if effective else 999
        timing_score = _TIMING_FLOOR
        for threshold, score in _TIMING_TABLE:
            if days_to <= threshold:
                timing_score = score
                break

        match_score = round(
            _W_QUANTITY    * quantity_score
            + _W_DISTANCE    * distance_score
            + _W_PRICE       * price_score
            + _W_RELIABILITY * reliability_score
            + _W_TIMING      * timing_score,
            4,
        )

        return {
            "declaration_id":    ctx.declaration_id,
            "match_score":       match_score,
            "quantity_score":    round(quantity_score, 4),
            "distance_score":    round(distance_score, 4),
            "price_score":       round(price_score, 4),
            "reliability_score": round(reliability_score, 4),
            "timing_score":      round(timing_score, 4),
            "distance_km":       round(ctx.road_km, 1),
        }

    # ── Serialiser ────────────────────────────────────────────────────────────

    @staticmethod
    def _serialize_listing(row, scores: dict, delivery_cost: float, cost_per_kg: float) -> dict:
        f_price   = _f(row.price_forecast_ghs) if row.price_forecast_ghs else 0.0
        full_name = str(row.farmer_name) if row.farmer_name else "Unknown"
        adj       = row.adjusted_harvest_date
        return {
            "declaration_id":        int(row.id),
            "farmer_name":           full_name.split()[0] if full_name else "Unknown",
            "district":              row.district_name,
            "region":                row.region_name,
            "quantity_kg":           float(row.quantity_kg),
            "harvest_date":          str(row.harvest_date),
            "adjusted_harvest_date": str(adj) if adj else str(row.harvest_date),
            "price_forecast_ghs":    round(f_price, 2),
            "delivery_cost_ghs":     round(delivery_cost, 2),
            "landed_cost_per_kg":    round(f_price + cost_per_kg, 2),
            "match_score":           scores["match_score"],
            "quantity_score":        scores["quantity_score"],
            "distance_score":        scores["distance_score"],
            "price_score":           scores["price_score"],
            "reliability_score":     scores["reliability_score"],
            "timing_score":          scores["timing_score"],
            "csi_flag":              row.csi_flag or "normal",
            "distance_km":           scores["distance_km"],
        }

    # ── Method 1: score_listing ──────────────────────────────────────────────

    def score_listing(
        self,
        declaration_id: int,
        buyer_district_id: int,
        quantity_kg_needed: float,
    ) -> Optional[dict]:
        """Score a single listing for a buyer query. Returns all sub-scores."""
        with get_session() as db:
            decl = MatchmakingRepo.get_declaration_for_scoring(db, declaration_id)
            if decl is None:
                return None
            road_km  = MatchmakingRepo.get_road_km(db, int(decl.district_id), buyer_district_id)
            mp_row   = MatchmakingRepo.get_median_price(db, str(decl.crop))
            median_price = _f(mp_row.median_price) if mp_row else 0.0

        ctx = ScoringContext(
            declaration_id        = declaration_id,
            district_id           = int(decl.district_id),
            quantity_kg           = float(decl.quantity_kg),
            harvest_date          = decl.harvest_date,
            adjusted_harvest_date = decl.adjusted_harvest_date,
            price_forecast_ghs    = decl.price_forecast_ghs,
            csi_flag              = decl.csi_flag,
            buyer_district_id     = buyer_district_id,
            quantity_kg_needed    = quantity_kg_needed,
            road_km               = road_km,
            median_price          = median_price,
        )
        return self._compute_scores(ctx)

    # ── Method 2: search ─────────────────────────────────────────────────────

    def search(
        self,
        crop: str,
        buyer_district_id: int,
        quantity_kg_needed: float,
        max_results: int = 20,
        filters: Optional[dict] = None,
    ) -> dict:
        """Return ranked, enriched listings for a buyer query."""
        filters = filters or {}
        today          = date.today()
        harvest_before = filters.get("harvest_before", today + timedelta(days=90))
        logi_vehicle, logi_tier = _vehicle_tier(quantity_kg_needed)

        sql_params: dict = {
            "crop":       crop,
            "buyer_did":  buyer_district_id,
            "hfrom":      today,
            "hto":        harvest_before,
            "logi_vtype": logi_vehicle,
            "logi_cargo": logi_tier,
        }

        with get_session() as db:
            rows = MatchmakingRepo.search_listings(
                db,
                sql_params,
                exclude_csi=bool(filters.get("exclude_csi")),
                min_qty   =float(filters["min_quantity_kg"]) if filters.get("min_quantity_kg") is not None else None,
                max_price =float(filters["max_price_ghs"])   if filters.get("max_price_ghs")   is not None else None,
            )
            mp_row       = MatchmakingRepo.get_median_price(db, crop)
            median_price = _f(mp_row.median_price) if mp_row else 0.0
            buyer_name   = MatchmakingRepo.get_buyer_district_name(db, buyer_district_id)

        max_dist = filters.get("max_distance_km")
        if max_dist is not None:
            rows = [
                r for r in rows
                if int(r.district_id) == buyer_district_id
                or _f(r.road_distance_km) <= float(max_dist)
            ]

        scored = []
        for row in rows:
            road_km       = _f(row.road_distance_km)
            delivery_cost = _f(row.delivery_cost_ghs)
            cost_per_kg   = _f(row.cost_per_kg_ghs)

            ctx = ScoringContext(
                declaration_id        = int(row.id),
                district_id           = int(row.district_id),
                quantity_kg           = float(row.quantity_kg),
                harvest_date          = row.harvest_date,
                adjusted_harvest_date = row.adjusted_harvest_date,
                price_forecast_ghs    = row.price_forecast_ghs,
                csi_flag              = row.csi_flag,
                buyer_district_id     = buyer_district_id,
                quantity_kg_needed    = quantity_kg_needed,
                road_km               = road_km,
                median_price          = median_price,
            )
            scores = self._compute_scores(ctx)
            scored.append(self._serialize_listing(row, scores, delivery_cost, cost_per_kg))

        scored.sort(key=lambda x: x["match_score"], reverse=True)

        return {
            "crop": crop,
            "query": {
                "buyer_district_id":   buyer_district_id,
                "buyer_district_name": buyer_name,
                "quantity_kg":         quantity_kg_needed,
                "filters":             filters,
            },
            "total_found": len(scored),
            "results":     scored[:max_results],
        }

    # ── Method 3: get_market_overview ────────────────────────────────────────

    def get_market_overview(self, crop: str) -> dict:
        """Return a market-level summary for buyers researching a crop."""
        today      = date.today()
        window_to  = today + timedelta(days=90)
        date_range = {"crop": crop, "hfrom": today, "hto": window_to}

        with get_session() as db:
            summary    = MatchmakingRepo.get_market_summary(db, date_range)
            csi_rows   = MatchmakingRepo.get_csi_distribution(db, date_range)
            regional   = MatchmakingRepo.get_regional_supply(db, date_range)
            surge_rows = MatchmakingRepo.get_surge_weeks(db, date_range)

        total_for_pct = sum(int(r.cnt) for r in csi_rows) or 1
        csi_dist = {
            str(r.flag): {
                "count": int(r.cnt),
                "pct":   round(int(r.cnt) / total_for_pct * 100, 1),
            }
            for r in csi_rows
        }

        return {
            "crop":                   crop,
            "window":                 f"{today} to {window_to}",
            "active_listings":        int(summary.listing_count) if summary else 0,
            "total_active_supply_kg": float(summary.total_supply_kg) if summary else 0.0,
            "median_price_ghs":       round(_f(summary.median_price), 2) if summary else 0.0,
            "price_range": {
                "min_ghs": round(_f(summary.min_price), 2) if summary else 0.0,
                "max_ghs": round(_f(summary.max_price), 2) if summary else 0.0,
            },
            "csi_risk_distribution": csi_dist,
            "regional_supply": [
                {
                    "region":        r.region_name,
                    "listing_count": int(r.listing_count),
                    "supply_kg":     float(r.supply_kg),
                }
                for r in regional
            ],
            "harvest_surge_weeks": [
                {
                    "week_start": str(r.week_start)[:10],
                    "listings":   int(r.listings),
                }
                for r in surge_rows
            ],
        }
