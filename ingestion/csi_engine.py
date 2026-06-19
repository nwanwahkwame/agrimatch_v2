"""
M6 - Crop Stress Index (CSI) engine for AgriMatch.

Reads pre-computed CSI values from climate_indicators and applies
them to active farmer_declarations, adjusting harvest dates and flags.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, text

from db.connection import get_session
from db.models import ClimateIndicator, FarmerDeclaration

logger = logging.getLogger(__name__)

_CSI_COLS = {
    "maize":    "csi_maize",
    "tomato":   "csi_tomato",
    "onion":    "csi_onion",
    "cassava":  "csi_cassava",
    "rice":     "csi_rice",
    "plantain": "csi_plantain",
}


class CSIEngine:

    def get_csi_for_declaration(self, declaration_id: int) -> Optional[dict]:
        """Return current CSI data for a declaration based on its crop and district.

        Returns None if the declaration does not exist.
        """
        with get_session() as db:
            decl = db.execute(
                select(FarmerDeclaration).where(FarmerDeclaration.id == declaration_id)
            ).scalar_one_or_none()
            if decl is None:
                return None

            district_id = decl.district_id
            crop = (decl.crop or "").lower()

            row = db.execute(
                select(ClimateIndicator)
                .where(ClimateIndicator.district_id == district_id)
                .order_by(ClimateIndicator.indicator_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if row is None:
                return {
                    "csi_value": None,
                    "flag_level": "normal",
                    "harvest_delay_days": 0,
                    "indicator_date": None,
                }

            csi_col = _CSI_COLS.get(crop)
            csi_value = getattr(row, csi_col, None) if csi_col else None

            return {
                "csi_value": float(csi_value) if csi_value is not None else None,
                "flag_level": row.flag_level or "normal",
                "harvest_delay_days": row.harvest_delay_days or 0,
                "indicator_date": row.indicator_date,
            }

    def update_declaration_csi(self, declaration_id: int) -> dict:
        """Update csi_flag and adjusted_harvest_date from current climate data.

        Returns a dict describing what changed.
        """
        csi = self.get_csi_for_declaration(declaration_id)
        if csi is None:
            return {
                "was_updated": False,
                "old_flag": None,
                "new_flag": None,
                "old_adjusted_date": None,
                "new_adjusted_date": None,
            }

        with get_session() as db:
            decl = db.execute(
                select(FarmerDeclaration).where(FarmerDeclaration.id == declaration_id)
            ).scalar_one_or_none()
            if decl is None:
                return {
                    "was_updated": False,
                    "old_flag": None,
                    "new_flag": None,
                    "old_adjusted_date": None,
                    "new_adjusted_date": None,
                }

            old_flag = decl.csi_flag
            old_adjusted_date = decl.adjusted_harvest_date

            new_flag = csi["flag_level"]
            delay = csi["harvest_delay_days"]
            new_adjusted_date = decl.harvest_date + timedelta(days=delay)

            was_updated = (old_flag != new_flag) or (old_adjusted_date != new_adjusted_date)

            decl.csi_flag = new_flag
            decl.adjusted_harvest_date = new_adjusted_date
            decl.updated_at = datetime.now(timezone.utc)

        return {
            "was_updated": was_updated,
            "old_flag": old_flag,
            "new_flag": new_flag,
            "old_adjusted_date": old_adjusted_date,
            "new_adjusted_date": new_adjusted_date,
        }

    def run_all_active(self) -> dict:
        """Update CSI for all declarations with status='active'.

        Returns summary with total processed and change counts.
        """
        with get_session() as db:
            ids = db.execute(
                select(FarmerDeclaration.id).where(FarmerDeclaration.status == "active")
            ).scalars().all()

        total = len(ids)
        flag_changed = 0
        date_adjusted = 0
        moved_to_alert = 0

        for did in ids:
            result = self.update_declaration_csi(did)
            if result["old_flag"] != result["new_flag"]:
                flag_changed += 1
            if result["old_adjusted_date"] != result["new_adjusted_date"]:
                date_adjusted += 1
            if (
                result["new_flag"] in ("warning", "critical")
                and result.get("old_flag") not in ("warning", "critical")
            ):
                moved_to_alert += 1

        logger.info(
            "run_all_active: %d processed, %d flags changed, %d dates adjusted, "
            "%d newly alerted",
            total, flag_changed, date_adjusted, moved_to_alert,
        )
        return {
            "total_processed": total,
            "flag_changed": flag_changed,
            "date_adjusted": date_adjusted,
            "moved_to_alert": moved_to_alert,
        }

    def check_and_alert(self, declaration_id: int) -> Optional[dict]:
        """Update declaration and return an alert payload if flag moved to warning or critical.

        Returns None if no alert is needed (flag is normal/watch, or nothing changed).
        The actual SMS delivery is handled by M17; this method only generates the payload.
        """
        result = self.update_declaration_csi(declaration_id)
        if result["new_flag"] not in ("warning", "critical"):
            return None
        if not result["was_updated"]:
            return None

        with get_session() as db:
            decl = db.execute(
                select(FarmerDeclaration).where(FarmerDeclaration.id == declaration_id)
            ).scalar_one_or_none()
            if decl is None:
                return None

            farmer_id = decl.farmer_id
            crop = decl.crop
            district = str(decl.district_id)
            harvest_date = decl.harvest_date

        delay = (
            (result["new_adjusted_date"] - harvest_date).days
            if result["new_adjusted_date"] else 0
        )
        new_flag = result["new_flag"]
        alert_msg = (
            f"ALERT: {crop.title()} harvest delayed {delay}d due to "
            f"{new_flag} stress. New date: {result['new_adjusted_date']}"
        )[:160]

        return {
            "farmer_id": farmer_id,
            "crop": crop,
            "district": district,
            "old_flag": result["old_flag"],
            "new_flag": new_flag,
            "old_harvest_date": harvest_date,
            "new_harvest_date": result["new_adjusted_date"],
            "delay_days": delay,
            "alert_message": alert_msg,
        }

    def get_district_risk_summary(self) -> list[dict]:
        """Return per-region CSI risk distribution from the latest climate_indicators date.

        Groups by region and flag_level. Powers the CSI risk map on the dashboard.
        """
        with get_session() as db:
            latest_date = db.execute(
                select(ClimateIndicator.indicator_date)
                .order_by(ClimateIndicator.indicator_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest_date is None:
                return []

            rows = db.execute(
                text("""
                    SELECT
                        gd.region_name,
                        ci.flag_level,
                        COUNT(*) AS district_count,
                        ROUND(AVG(ci.spi_30day)::numeric, 3) AS avg_spi,
                        ROUND(AVG(ci.et0_mm)::numeric, 3) AS avg_et0
                    FROM climate_indicators ci
                    JOIN ghana_districts gd ON gd.id = ci.district_id
                    WHERE ci.indicator_date = :dt
                    GROUP BY gd.region_name, ci.flag_level
                    ORDER BY gd.region_name, ci.flag_level
                """),
                {"dt": latest_date},
            ).fetchall()

        return [
            {
                "region": r[0],
                "flag_level": r[1],
                "district_count": r[2],
                "avg_spi": float(r[3]) if r[3] is not None else None,
                "avg_et0": float(r[4]) if r[4] is not None else None,
                "as_of": latest_date,
            }
            for r in rows
        ]
