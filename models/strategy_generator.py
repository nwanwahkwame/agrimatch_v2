"""
Strategy generator for AgriMatch (M13).

Produces plain-English action cards for farmers (sell timing),
buyers (sourcing opportunities), and logistics (truck sharing).
Injected with xgb_predictor and lstm_predictor at startup.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.connection import get_session
from db.repositories.strategy_repo import StrategyRepo
from utils.geo import haversine as _hav
from utils.math_utils import safe_float as _f

logger = logging.getLogger(__name__)

_URGENCY_ORDER = {"sell_now": 0, "sell_soon": 1, "neutral": 2, "wait": 3}


class StrategyGenerator:

    def __init__(self):
        self.xgb_predictor  = None
        self.lstm_predictor = None
        self._logistics     = None  # injected at startup via app.state
        self._market_cache: dict = {}

    # ── Nearest market helper ────────────────────────────────────────────────

    def _nearest_market(self, district_id: int) -> Optional[tuple]:
        """Return (canonical_name, market_district_id) closest to district_id."""
        if district_id in self._market_cache:
            return self._market_cache[district_id]

        with get_session() as db:
            origin = StrategyRepo.get_district_centroid(db, district_id)

        if origin is None:
            return None

        olat = _f(origin.centroid_lat)
        olon = _f(origin.centroid_lon)

        with get_session() as db:
            markets = StrategyRepo.get_all_markets_with_coords(db)

        if not markets:
            return None

        nearest = min(
            markets,
            key=lambda m: _hav(olat, olon, _f(m.centroid_lat), _f(m.centroid_lon)),
        )
        result = (nearest.canonical_name, int(nearest.district_id))
        self._market_cache[district_id] = result
        return result

    # ── Forecast helpers ─────────────────────────────────────────────────────

    def _price_at(self, forecasts: list, horizon: int) -> Optional[float]:
        for f in forecasts:
            if f.get("horizon_days") == horizon:
                return _f(f.get("predicted_price_ghs"))
        return _f(forecasts[-1]["predicted_price_ghs"]) if forecasts else None

    def _direction_at(self, forecasts: list, horizon: int) -> str:
        for f in forecasts:
            if f.get("horizon_days") == horizon:
                return f.get("direction", "stable")
        return "stable"

    # ── Method 1: Farmer sell strategy ───────────────────────────────────────

    def farmer_sell_strategy(self, declaration_id: int) -> Optional[dict]:
        """Build a sell-timing action card for an active declaration."""
        with get_session() as db:
            decl = StrategyRepo.get_active_declaration(db, declaration_id)

        if decl is None:
            logger.warning("Declaration %s not found or not active", declaration_id)
            return None

        market_info = self._nearest_market(decl.district_id)
        if market_info is None:
            logger.warning("No linked market for district %s", decl.district_id)
            return None
        market_name, market_district_id = market_info

        xgb = self.xgb_predictor.predict(decl.crop, market_name) if self.xgb_predictor else None
        if xgb is None:
            logger.warning("No XGBoost forecast for %s/%s", decl.crop, market_name)
            return None

        lstm = self.lstm_predictor.predict(decl.crop, market_name) if self.lstm_predictor else None

        last_price = _f(xgb.get("last_known_price"))
        xgb_30d    = self._price_at(xgb.get("forecasts", []), 30)
        xgb_60d    = self._price_at(xgb.get("forecasts", []), 60)
        xgb_dir    = self._direction_at(xgb.get("forecasts", []), 30)

        if lstm:
            lstm_30d     = self._price_at(lstm.get("forecasts", []), 30)
            lstm_60d     = self._price_at(lstm.get("forecasts", []), 60)
            ensemble_30d = (0.5 * xgb_30d + 0.5 * lstm_30d) if lstm_30d else xgb_30d
            forecast_60d = (0.5 * xgb_60d + 0.5 * lstm_60d) if lstm_60d else xgb_60d
        else:
            ensemble_30d = xgb_30d or 0.0
            forecast_60d = xgb_60d or 0.0

        if not self._logistics:
            logger.error("StrategyGenerator._logistics not injected at startup")
            return None

        quantity    = float(decl.quantity_kg)
        logistics   = self._logistics.get_delivery_cost(decl.district_id, market_district_id, quantity)
        cost_per_kg = _f(logistics["cost_per_kg_ghs"]) if logistics else 0.0
        net_per_kg  = max(0.0, ensemble_30d - cost_per_kg)
        total_net   = net_per_kg * quantity

        stored    = _f(decl.price_forecast_ghs) if decl.price_forecast_ghs else last_price
        ref_price = stored if stored > 0 else last_price

        price_change_pct = (
            round((ensemble_30d - last_price) / last_price * 100, 1)
            if last_price > 0 else 0.0
        )

        csi_flag = decl.csi_flag or "normal"

        if csi_flag in ("warning", "critical"):
            urgency = "sell_soon"
            timing  = (
                "Climate stress detected in your district. Consider selling earlier "
                "than planned to avoid harvest delays."
            )
        elif xgb_dir == "up" and xgb_30d and xgb_30d > ref_price * 1.08:
            urgency = "wait"
            pct     = abs(price_change_pct)
            timing  = (
                f"Prices forecast to rise {pct:.1f}% over the next 30 days. "
                "Waiting is likely profitable."
            )
        elif xgb_30d and xgb_30d < ref_price * 0.95:
            urgency = "sell_now"
            timing  = (
                "Prices forecast to dip. Selling now captures the current price "
                "before the drop."
            )
        else:
            urgency = "neutral"
            timing  = "Prices are stable. Sell when ready."

        target_date = decl.adjusted_harvest_date or decl.harvest_date
        headline = (
            f"Sell {decl.crop} by {target_date} at {market_name} "
            f"(net GHS {net_per_kg:.2f}/kg)"
        )[:80]

        body = (
            f"{timing} "
            f"After delivery costs of GHS {cost_per_kg:.2f}/kg to {market_name}, "
            f"your expected net income is GHS {total_net:,.0f} for "
            f"{quantity:,.0f} kg of {decl.crop}."
        )

        action = f"Arrange transport to {market_name}. Target sale date: {target_date}."

        return {
            "declaration_id": declaration_id,
            "farmer_id":      decl.farmer_id,
            "crop":           decl.crop,
            "strategy_type":  "farmer_sell",
            "urgency":        urgency,
            "headline":       headline,
            "body":           body,
            "action":         action,
            "numbers": {
                "current_price_ghs":         round(last_price, 2),
                "forecast_30d_ghs":          round(ensemble_30d, 2),
                "forecast_60d_ghs":          round(forecast_60d, 2),
                "net_after_delivery_ghs":    round(net_per_kg, 2),
                "total_expected_income_ghs": round(total_net, 2),
                "price_change_pct":          price_change_pct,
            },
            "csi_flag":     csi_flag,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Method 2: Buyer sourcing strategy ────────────────────────────────────

    def buyer_sourcing_strategy(
        self,
        crop: str,
        buyer_district_id: int,
        quantity_kg_needed: float,
    ) -> Optional[dict]:
        """Build a buy-timing + supplier shortlist card for a buyer."""
        market_info = self._nearest_market(buyer_district_id)
        if market_info is None:
            logger.warning("No linked market for buyer district %s", buyer_district_id)
            return None
        market_name, _ = market_info

        xgb = self.xgb_predictor.predict(crop, market_name) if self.xgb_predictor else None
        if xgb is None:
            logger.warning("No XGBoost forecast for %s/%s", crop, market_name)
            return None

        last_price = _f(xgb.get("last_known_price"))
        xgb_30d    = self._price_at(xgb.get("forecasts", []), 30) or 0.0
        xgb_dir    = self._direction_at(xgb.get("forecasts", []), 30)

        if xgb_dir == "down" and xgb_30d < last_price:
            buy_timing    = "wait"
            wait_days     = 30
            saving_per_kg = round(last_price - xgb_30d, 2)
        else:
            buy_timing    = "buy_now"
            wait_days     = 0
            saving_per_kg = 0.0

        total_saving = round(saving_per_kg * quantity_kg_needed, 2)

        with get_session() as db:
            listings_raw = StrategyRepo.get_nearby_supplier_listings(db, crop, buyer_district_id)

        available = []
        for row in listings_raw:
            logi = (
                self._logistics.get_delivery_cost(
                    int(row.district_id), buyer_district_id, quantity_kg_needed
                ) if self._logistics else None
            )
            delivery_cost = _f(logi["total_cost_ghs"])  if logi else 0.0
            cost_per_kg   = _f(logi["cost_per_kg_ghs"]) if logi else 0.0
            f_price = _f(row.price_forecast_ghs) if row.price_forecast_ghs else last_price
            available.append({
                "declaration_id":         int(row.id),
                "farmer_district":        row.district_name,
                "distance_km":            round(_f(row.road_distance_km), 1),
                "quantity_kg":            float(row.quantity_kg),
                "harvest_date":           str(row.harvest_date),
                "price_forecast_ghs":     round(f_price, 2),
                "delivery_cost_ghs":      round(delivery_cost, 2),
                "landed_cost_per_kg_ghs": round(f_price + cost_per_kg, 2),
            })

        if buy_timing == "wait":
            headline = (
                f"Wait {wait_days} days to buy {crop} - prices forecast to fall "
                f"GHS {saving_per_kg:.2f}/kg"
            )[:80]
            body = (
                f"Prices for {crop} are forecast to drop by GHS {saving_per_kg:.2f}/kg "
                f"over the next {wait_days} days at {market_name}. "
                f"Waiting could save you GHS {total_saving:,.0f} on your "
                f"{quantity_kg_needed:,.0f} kg order."
            )
            action = f"Hold off purchasing for {wait_days} days. Monitor prices in {market_name}."
        else:
            headline = f"Buy {crop} now - prices stable or rising at {market_name}"[:80]
            body = (
                f"Prices for {crop} are expected to hold steady or rise at "
                f"{market_name}. Waiting is unlikely to save money. "
                f"There are {len(available)} active supplier(s) harvesting within 60 days."
            )
            action = (
                f"Contact available suppliers and arrange purchase of "
                f"{quantity_kg_needed:,.0f} kg of {crop}."
            )

        return {
            "crop":          crop,
            "strategy_type": "buyer_sourcing",
            "buy_timing":    buy_timing,
            "headline":      headline,
            "body":          body,
            "action":        action,
            "numbers": {
                "current_price_ghs":       round(last_price, 2),
                "forecast_30d_ghs":        round(xgb_30d, 2),
                "saving_per_kg_if_wait":   saving_per_kg,
                "total_saving_ghs":        total_saving,
            },
            "available_listings": available,
            "generated_at":       datetime.now(timezone.utc).isoformat(),
        }

    # ── Method 3: Logistics sharing strategy ─────────────────────────────────

    def logistics_strategy(self, declaration_id: int) -> Optional[dict]:
        """Find nearby declarations that could share a truck."""
        with get_session() as db:
            decl = StrategyRepo.get_logistics_declaration(db, declaration_id)

        if decl is None:
            return None

        window_from = decl.harvest_date - timedelta(days=3)
        window_to   = decl.harvest_date + timedelta(days=3)

        with get_session() as db:
            nearby_raw = StrategyRepo.get_nearby_declarations(
                db, declaration_id, decl.district_id, window_from, window_to
            )

        if len(nearby_raw) < 1:
            return None

        market_info = self._nearest_market(decl.district_id)
        if market_info is None:
            return None
        _, market_district_id = market_info

        if not self._logistics:
            logger.error("StrategyGenerator._logistics not injected at startup")
            return None

        individual = self._logistics.get_delivery_cost(
            decl.district_id, market_district_id, float(decl.quantity_kg)
        )
        individual_cost = _f(individual["total_cost_ghs"]) if individual else 0.0

        total_shared_kg = float(decl.quantity_kg) + sum(
            float(r.quantity_kg) for r in nearby_raw
        )
        shared = self._logistics.get_delivery_cost(
            decl.district_id, market_district_id, total_shared_kg
        )
        shared_total = _f(shared["total_cost_ghs"]) if shared else 0.0
        n_partners   = len(nearby_raw)
        my_share     = shared_total / (n_partners + 1)
        saving       = max(0.0, individual_cost - my_share)

        farms = [
            {
                "declaration_id": int(r.id),
                "farmer_name":    r.farmer_name,
                "district":       r.district_name,
                "quantity_kg":    float(r.quantity_kg),
                "harvest_date":   str(r.harvest_date),
                "distance_km":    round(_f(r.road_distance_km), 1),
            }
            for r in nearby_raw
        ]

        headline = (
            f"Save GHS {saving:,.0f} by sharing a truck with {n_partners} nearby farm(s)"
        )[:80]

        body = (
            f"There are {n_partners} farm(s) near you harvesting within 3 days of your "
            f"harvest date. Sharing a truck cuts your transport cost from "
            f"GHS {individual_cost:,.0f} to GHS {my_share:,.0f}."
        )

        return {
            "declaration_id": declaration_id,
            "strategy_type":  "logistics_sharing",
            "urgency":        "neutral",
            "headline":       headline,
            "body":           body,
            "action":         "Contact the platform to confirm shared transport with the farms listed below.",
            "numbers": {
                "individual_transport_ghs": round(individual_cost, 2),
                "shared_transport_ghs":     round(my_share, 2),
                "saving_ghs":               round(saving, 2),
                "n_partners":               n_partners,
            },
            "farms":        farms,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Method 4: All strategies for a farmer ────────────────────────────────

    def generate_all_for_farmer(self, farmer_id: int) -> list:
        """Return all sell and logistics strategy cards for a farmer's active declarations."""
        with get_session() as db:
            decls = StrategyRepo.get_active_declaration_ids(db, farmer_id)

        cards = []
        for row in decls:
            sell = self.farmer_sell_strategy(int(row.id))
            if sell:
                cards.append(sell)
            logi = self.logistics_strategy(int(row.id))
            if logi:
                cards.append(logi)

        cards.sort(key=lambda c: _URGENCY_ORDER.get(c.get("urgency", "neutral"), 99))
        return cards
