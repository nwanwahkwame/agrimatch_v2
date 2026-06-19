"""
Crop recommender for AgriMatch (M12).

Scores all 16 crops for a district using climate stress, regional supply,
and price momentum signals, then returns a ranked recommendation list.
"""

import logging
from datetime import date, timedelta

from db.connection import get_session
from db.repositories.crop_recommender_repo import CropRecommenderRepo
from utils.geo import haversine as _haversine_km
from utils.math_utils import safe_float as _f

logger = logging.getLogger(__name__)

_ALL_CROPS = [
    "maize", "tomato", "onion", "cassava", "yam", "plantain",
    "rice", "sorghum", "groundnut", "pepper", "cowpea", "millet",
    "cocoyam", "garden_egg", "ginger", "soybean",
]

_CSI_COLUMN = {
    "maize":    "csi_maize",
    "tomato":   "csi_tomato",
    "onion":    "csi_onion",
    "cassava":  "csi_cassava",
    "rice":     "csi_rice",
    "plantain": "csi_plantain",
}

_SUPPLY_BENCHMARK = {
    "maize":     500_000,
    "cassava":   500_000,
    "yam":       500_000,
    "tomato":     50_000,
    "pepper":     50_000,
    "onion":      50_000,
    "rice":      200_000,
    "sorghum":   200_000,
    "millet":    200_000,
    "plantain":  300_000,
}
_DEFAULT_BENCHMARK = 100_000

_STRENGTH_THRESHOLDS = [
    (0.75, "strongly recommended"),
    (0.60, "recommended"),
    (0.45, "consider"),
    (0.30, "caution"),
    (0.00, "avoid"),
]

_W_CLIMATE = 0.40
_W_SUPPLY  = 0.35
_W_PRICE   = 0.25


def _strength(composite: float) -> str:
    for threshold, label in _STRENGTH_THRESHOLDS:
        if composite >= threshold:
            return label
    return "avoid"


class CropRecommender:

    def __init__(self):
        self.xgb_predictor = None   # injected from app.state at startup

    # ── Climate score ────────────────────────────────────────────────────────

    def get_climate_score(self, district_id: int, crop: str) -> float:
        """Return 0-1 score; 1.0 = ideal conditions, 0.0 = severe stress."""
        with get_session() as db:
            row = CropRecommenderRepo.get_climate_indicators_latest(db, district_id)

        if row is None:
            return 0.5

        csi_col = _CSI_COLUMN.get(crop)
        if csi_col:
            csi = _f(getattr(row, csi_col, None))
            return max(0.0, min(1.0, 1.0 - csi))
        else:
            csi_maize = _f(row.csi_maize)
            return max(0.0, min(1.0, 1.0 - (csi_maize * 0.8)))

    # ── Supply score ─────────────────────────────────────────────────────────

    def get_supply_score(
        self,
        district_id: int,
        crop: str,
        weeks_ahead: int = 12,
    ) -> float:
        """Return 0-1 score; 1.0 = very low regional supply (market opportunity)."""
        harvest_from = date.today()
        harvest_to   = harvest_from + timedelta(weeks=weeks_ahead)

        with get_session() as db:
            row = CropRecommenderRepo.get_regional_supply(
                db, district_id, crop, harvest_from, harvest_to
            )

        total_kg  = float(row.total_kg) if row and row.total_kg else 0.0
        benchmark = _SUPPLY_BENCHMARK.get(crop, _DEFAULT_BENCHMARK)
        return max(0.0, min(1.0, 1.0 - total_kg / benchmark))

    # ── Price score ──────────────────────────────────────────────────────────

    def get_price_score(self, crop: str, district_id: int) -> float:
        """Return 0-1 score based on 90-day price momentum in the nearest market."""
        if self.xgb_predictor is None:
            return 0.5

        with get_session() as db:
            dist_row = CropRecommenderRepo.get_district_coords(db, district_id)
            markets  = CropRecommenderRepo.get_markets_with_coords(db)

        if dist_row is None:
            return 0.5

        dlat = _f(dist_row.centroid_lat)
        dlon = _f(dist_row.centroid_lon)

        if not markets:
            return 0.5

        nearest = min(
            markets,
            key=lambda m: _haversine_km(
                dlat, dlon,
                _f(m.centroid_lat), _f(m.centroid_lon),
            ),
        )

        forecast = self.xgb_predictor.predict(crop, nearest.canonical_name)
        if forecast is None:
            return 0.5

        last_price = forecast.get("last_known_price", 0.0)
        if not last_price or last_price <= 0:
            return 0.5

        target = None
        for f in forecast.get("forecasts", []):
            if f["horizon_days"] == 90:
                target = f
                break
        if target is None and forecast.get("forecasts"):
            target = forecast["forecasts"][-1]
        if target is None:
            return 0.5

        momentum = (target["predicted_price_ghs"] - last_price) / last_price

        if momentum >= 0.20:
            raw = 1.0
        elif momentum >= 0.10:
            raw = 0.8
        elif momentum >= 0.0:
            raw = 0.6
        elif momentum >= -0.10:
            raw = 0.4
        else:
            raw = 0.2

        confidence = forecast.get("confidence", 1.0)
        return max(0.0, min(1.0, raw * confidence))

    # ── Reason ───────────────────────────────────────────────────────────────

    def _reason(
        self,
        crop: str,
        climate: float,
        supply: float,
        price: float,
    ) -> str:
        w_climate = _W_CLIMATE * climate
        w_supply  = _W_SUPPLY  * supply
        w_price   = _W_PRICE   * price

        if w_climate >= w_supply and w_climate >= w_price:
            if climate >= 0.7:
                return "Excellent growing conditions in your district with low drought risk."
            elif climate >= 0.4:
                return "Moderate growing conditions with manageable climate stress in your district."
            else:
                return "Difficult growing conditions due to drought or high climate stress in your area."
        elif w_supply >= w_price:
            if supply >= 0.7:
                return "Low regional supply means less competition and stronger market prices at harvest."
            elif supply >= 0.4:
                return "Moderate supply levels in your region leave room for profitable sales."
            else:
                return "High regional supply may put downward pressure on prices at harvest time."
        else:
            if price >= 0.7:
                return f"Prices for {crop} are forecast to rise strongly in your nearest market over the next 3 months."
            elif price >= 0.4:
                return f"Prices for {crop} are expected to hold steady or rise moderately in your nearest market."
            else:
                return f"Prices for {crop} are forecast to decline in your nearest market over the next 3 months."

    # ── Recommend ────────────────────────────────────────────────────────────

    def _prefetch_bulk(self, district_id: int) -> dict:
        """Fetch all district-level data in one session to avoid N round-trips."""
        harvest_from = date.today()
        harvest_to   = harvest_from + timedelta(weeks=12)

        with get_session() as db:
            dist_row, climate_row, markets, supply_rows = CropRecommenderRepo.get_bulk_data(
                db, district_id, list(_ALL_CROPS), harvest_from, harvest_to
            )

        supply_map: dict[str, float] = {r.crop: float(r.total_kg) for r in supply_rows}

        nearest_market = None
        if dist_row and markets:
            dlat = _f(dist_row.centroid_lat)
            dlon = _f(dist_row.centroid_lon)
            nearest = min(
                markets,
                key=lambda m: _haversine_km(
                    dlat, dlon, _f(m.centroid_lat), _f(m.centroid_lon)
                ),
            )
            nearest_market = nearest.canonical_name

        return {
            "climate_row":    climate_row,
            "supply_map":     supply_map,
            "nearest_market": nearest_market,
        }

    def _climate_from_cache(self, climate_row, crop: str) -> float:
        if climate_row is None:
            return 0.5
        csi_col = _CSI_COLUMN.get(crop)
        if csi_col:
            csi = _f(getattr(climate_row, csi_col, None))
            return max(0.0, min(1.0, 1.0 - csi))
        csi_maize = _f(climate_row.csi_maize)
        return max(0.0, min(1.0, 1.0 - (csi_maize * 0.8)))

    def _price_from_market(self, crop: str, market_name: str | None) -> float:
        if self.xgb_predictor is None or not market_name:
            return 0.5
        forecast = self.xgb_predictor.predict(crop, market_name)
        if forecast is None:
            return 0.5
        last_price = forecast.get("last_known_price", 0.0)
        if not last_price or last_price <= 0:
            return 0.5
        target = next(
            (f for f in forecast.get("forecasts", []) if f["horizon_days"] == 90),
            None,
        )
        if target is None and forecast.get("forecasts"):
            target = forecast["forecasts"][-1]
        if target is None:
            return 0.5
        momentum = (target["predicted_price_ghs"] - last_price) / last_price
        raw = (
            1.0 if momentum >= 0.20 else
            0.8 if momentum >= 0.10 else
            0.6 if momentum >= 0.0  else
            0.4 if momentum >= -0.10 else 0.2
        )
        return max(0.0, min(1.0, raw * forecast.get("confidence", 1.0)))

    def recommend(self, district_id: int, top_n: int = 5) -> list:
        """Score all crops and return top_n sorted by composite score."""
        bulk = self._prefetch_bulk(district_id)
        climate_row    = bulk["climate_row"]
        supply_map     = bulk["supply_map"]
        nearest_market = bulk["nearest_market"]

        results = []
        for crop in _ALL_CROPS:
            climate   = self._climate_from_cache(climate_row, crop)
            total_kg  = supply_map.get(crop, 0.0)
            benchmark = _SUPPLY_BENCHMARK.get(crop, _DEFAULT_BENCHMARK)
            supply    = max(0.0, min(1.0, 1.0 - total_kg / benchmark))
            price     = self._price_from_market(crop, nearest_market)
            composite = round(_W_CLIMATE * climate + _W_SUPPLY * supply + _W_PRICE * price, 4)

            results.append({
                "crop":                    crop,
                "composite_score":         composite,
                "climate_score":           round(climate, 4),
                "supply_score":            round(supply, 4),
                "price_score":             round(price, 4),
                "recommendation_strength": _strength(composite),
                "reason":                  self._reason(crop, climate, supply, price),
            })

        results.sort(key=lambda r: r["composite_score"], reverse=True)
        return results[:top_n]

    # ── Farmer-personalized recommend ────────────────────────────────────────

    def recommend_for_declaration(self, farmer_id: int) -> dict | None:
        """Return recommendations personalised with farmer name and district."""
        with get_session() as db:
            row = CropRecommenderRepo.get_farmer_info(db, farmer_id)

        if row is None:
            logger.warning("Farmer %s not found", farmer_id)
            return None

        if row.district_id is None:
            logger.warning("Farmer %s has no district_id", farmer_id)
            return None

        return {
            "farmer_id":       farmer_id,
            "farmer_name":     row.full_name,
            "district_id":     row.district_id,
            "district_name":   row.district_name,
            "recommendations": self.recommend(row.district_id),
        }
