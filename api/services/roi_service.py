from typing import Optional

from db.connection import get_session
from db.repositories.advisory_repo import AdvisoryRepo


class RoiService:

    @staticmethod
    def calculate(
        crop: str,
        quantity_kg: float,
        source_district_id: int,
        target_district_id: int,
        xgb,
        logistics,
    ) -> dict:
        # Single session: nearest market, fallback price, and both district names.
        with get_session() as db:
            mkt        = AdvisoryRepo.get_nearest_market(db, target_district_id)
            db_price   = AdvisoryRepo.get_latest_price(db, crop)
            src        = AdvisoryRepo.get_district_name(db, source_district_id)
            tgt        = AdvisoryRepo.get_district_name(db, target_district_id)

        market_name = str(mkt.canonical_name) if mkt else ""

        forecast_price: Optional[float] = None
        if market_name:
            pred = xgb.predict(crop, market_name)
            if pred:
                forecast_price = float(pred.get("last_known_price") or 0)
                forecasts = pred.get("forecasts", [])
                if forecasts:
                    forecast_price = float(
                        forecasts[0].get("predicted_price_ghs") or forecast_price
                    )

        if not forecast_price:
            forecast_price = float(db_price.price_ghs) if db_price else 0.0

        logi             = logistics.get_delivery_cost(source_district_id, target_district_id, quantity_kg)
        transport_cost   = float(logi["total_cost_ghs"])  if logi else 0.0
        transport_per_kg = float(logi["cost_per_kg_ghs"]) if logi else 0.0

        gross_revenue = round(forecast_price * quantity_kg, 2)
        net_revenue   = round(gross_revenue - transport_cost, 2)
        net_per_kg    = round(net_revenue / quantity_kg, 4) if quantity_kg else 0.0

        return {
            "crop":                  crop,
            "quantity_kg":           quantity_kg,
            "source_district":       str(src.district_name) if src else str(source_district_id),
            "target_district":       str(tgt.district_name) if tgt else str(target_district_id),
            "target_market":         market_name,
            "forecast_price_per_kg": round(forecast_price, 2),
            "gross_revenue_ghs":     gross_revenue,
            "transport_cost_ghs":    round(transport_cost, 2),
            "transport_per_kg_ghs":  round(transport_per_kg, 4),
            "net_revenue_ghs":       net_revenue,
            "net_per_kg_ghs":        net_per_kg,
            "margin_pct":            round((net_revenue / gross_revenue) * 100, 1) if gross_revenue else 0,
        }
