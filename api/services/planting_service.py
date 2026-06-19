import calendar
from datetime import date, timedelta
from typing import Optional

from config.crop_data import CROP_SEASONS
from db.connection import get_session
from db.repositories.advisory_repo import AdvisoryRepo


def _climate_risk(flag: str, csi: float) -> tuple:
    if flag == "critical" or csi > 0.75:
        return "high", "Drought stress is severe. Wait for rains before planting."
    if flag == "warning" or csi > 0.55:
        return "moderate", "Some climate stress detected. Monitor rainfall before planting."
    return "low", "Climate conditions are favourable for planting."


def _next_peak(today: date, peak_months: list) -> date:
    upcoming = []
    for m in peak_months:
        for yr_offset in [0, 1]:
            yr        = today.year + yr_offset
            last_day  = calendar.monthrange(yr, m)[1]
            peak_date = date(yr, m, min(15, last_day))
            if peak_date > today:
                upcoming.append(peak_date)
    upcoming.sort()
    return upcoming[0] if upcoming else date(today.year + 1, peak_months[0], 15)


def _planting_advice(days_to_plant: int) -> tuple:
    if days_to_plant <= 0:
        return "plant_now", "Plant immediately - peak price window approaching"
    if days_to_plant <= 14:
        return "plant_soon", f"Plant within {days_to_plant} days for best market timing"
    if days_to_plant <= 45:
        return "prepare", f"Prepare land - optimal plant date in {days_to_plant} days"
    return "wait", f"Wait {days_to_plant} days before planting"


class PlantingService:

    @staticmethod
    def get_advice(district_id: int, crop: str = "") -> dict:
        today = date.today()

        with get_session() as db:
            climate = AdvisoryRepo.get_climate(db, district_id)

        csi_map: dict = {}
        if climate:
            csi_map = {
                "maize":    float(climate.csi_maize    or 0),
                "tomato":   float(climate.csi_tomato   or 0),
                "cassava":  float(climate.csi_cassava  or 0),
                "onion":    float(climate.csi_onion    or 0),
                "rice":     float(climate.csi_rice     or 0),
                "plantain": float(climate.csi_plantain or 0),
            }
        flag = str(climate.flag_level) if climate else "normal"

        crops_to_check = (
            [crop] if crop and crop in CROP_SEASONS else list(CROP_SEASONS.keys())
        )
        results = []

        for c in crops_to_check:
            season      = CROP_SEASONS[c]
            grow_days   = season["days"]
            peak_months = season["peak_months"]

            peak      = _next_peak(today, peak_months)
            plant_on  = peak - timedelta(days=grow_days)
            days_left = (plant_on - today).days

            csi                        = csi_map.get(c, 0.3)
            climate_risk, climate_note = _climate_risk(flag, csi)
            advice, window_label       = _planting_advice(days_left)

            results.append({
                "crop":               c,
                "label":              season["label"],
                "growing_days":       grow_days,
                "optimal_plant_date": str(plant_on),
                "days_to_plant":      days_left,
                "next_peak_month":    peak.strftime("%B %Y"),
                "next_peak_date":     str(peak),
                "advice":             advice,
                "window_label":       window_label,
                "climate_risk":       climate_risk,
                "climate_note":       climate_note,
                "csi_score":          round(csi, 3),
            })

        results.sort(key=lambda r: r["days_to_plant"])
        return {"district_id": district_id, "generated_date": str(today), "crops": results}
