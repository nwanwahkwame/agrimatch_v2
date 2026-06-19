"""
Harvest delay classifier for AgriMatch (M11).

Predicts flag_level (normal/watch/warning/critical) and harvest_delay_days
for a district using recent climate indicators.
Model lives in models/m11/.
"""

import json
import logging
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np

from db.connection import get_session
from db.repositories.delay_classifier_repo import DelayClassifierRepo

logger = logging.getLogger(__name__)

_M11_DIR   = Path(__file__).parent / "m11"
_CLF_PATH  = _M11_DIR / "harvest_delay_classifier.pkl"
_COLS_PATH = _M11_DIR / "feature_columns.json"
_CFG_PATH  = _M11_DIR / "model_config.json"
_LMAP_PATH = _M11_DIR / "label_map.json"


def _safe_float(val) -> float:
    """Convert val to float, returning 0.0 on None, NaN, or type errors."""
    try:
        v = float(val)
        return 0.0 if v != v else v     # v != v is True only for NaN
    except (TypeError, ValueError):
        return 0.0


class HarvestDelayClassifier:

    def __init__(self):
        self.model              = None
        self.feature_cols: list = []
        self.config: dict       = {}
        self.inverse_label_map  = {0: "normal", 1: "watch", 2: "warning", 3: "critical"}
        self.delay_days_map     = {0: 0, 1: 3, 2: 9, 3: 18}

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_model(self) -> None:
        self.model = joblib.load(_CLF_PATH)

        with open(_COLS_PATH) as f:
            self.feature_cols = json.load(f)

        with open(_CFG_PATH) as f:
            self.config = json.load(f)

        with open(_LMAP_PATH) as f:
            lmap = json.load(f)
            self.inverse_label_map = {v: k for k, v in lmap.items()}

        delay_cfg = self.config.get("delay_days", {"0": 0, "1": 3, "2": 9, "3": 18})
        self.delay_days_map = {int(k): v for k, v in delay_cfg.items()}

        logger.info("Harvest delay classifier loaded (%d features)", len(self.feature_cols))

    # ── Feature engineering ───────────────────────────────────────────────────

    def _build_feature_vector(self, rows: list) -> np.ndarray:
        """Build the feature array in the order specified by self.feature_cols.

        Using the loaded column list rather than a hardcoded index order means
        this survives retraining even if the column order changes.
        Missing lag rows use 0.0 (zero-fill) rather than duplicating the latest
        row, which would silently corrupt the lag signal.
        """
        latest = rows[0]
        ind_date = latest.indicator_date

        # Named sources: each maps a feature name to its value
        sources: dict[str, float] = {
            "spi_30day":      _safe_float(latest.spi_30day),
            "et0_mm":         _safe_float(latest.et0_mm),
            "month":          float(ind_date.month),
            "day_of_year":    ind_date.timetuple().tm_yday / 365.0,
            "spi_30day_lag1": _safe_float(rows[1].spi_30day) if len(rows) >= 2 else 0.0,
            "spi_30day_lag3": _safe_float(rows[2].spi_30day) if len(rows) >= 3 else 0.0,
        }

        values = []
        for col in self.feature_cols:
            if col not in sources:
                logger.warning("Unknown feature column '%s'; defaulting to 0.0", col)
                values.append(0.0)
            else:
                values.append(sources[col])

        return np.array([values], dtype=np.float64)

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_delay(self, district_id: int) -> dict | None:
        """Return delay prediction for district_id using its latest climate rows."""
        if self.model is None:
            raise RuntimeError(
                "HarvestDelayClassifier.predict_delay() called before load_model()"
            )
        with get_session() as db:
            rows = DelayClassifierRepo.get_climate_indicators(db, district_id)

        if not rows:
            logger.warning("No climate_indicators rows for district %s", district_id)
            return None

        latest = rows[0]
        ind_date = latest.indicator_date
        x = self._build_feature_vector(rows)

        predicted_class = int(self.model.predict(x)[0])
        probabilities   = self.model.predict_proba(x)[0]
        confidence      = float(probabilities[predicted_class])

        return {
            "district_id":     district_id,
            "indicator_date":  str(ind_date),
            "predicted_class": predicted_class,
            "flag_level":      self.inverse_label_map[predicted_class],
            "delay_days":      self.delay_days_map[predicted_class],
            "confidence":      round(confidence, 4),
            "spi_30day":       _safe_float(latest.spi_30day),
            "et0_mm":          _safe_float(latest.et0_mm),
        }

    # ── Bulk declaration update ───────────────────────────────────────────────

    def update_all_active_declarations(self) -> dict:
        """Predict delay for every active declaration and update changed rows."""
        with get_session() as db:
            decls = DelayClassifierRepo.get_active_declarations(db)

        total   = len(decls)
        updated = 0

        for decl in decls:
            if decl.harvest_date is None:
                continue

            result = self.predict_delay(decl.district_id)
            if result is None:
                continue

            new_flag = result["flag_level"]
            new_date = decl.harvest_date + timedelta(days=result["delay_days"])

            flag_changed = new_flag != (decl.csi_flag or "normal")
            date_changed = new_date != decl.adjusted_harvest_date

            if flag_changed or date_changed:
                with get_session() as db:
                    DelayClassifierRepo.update_declaration_delay(
                        db, decl.id, new_flag, new_date
                    )
                updated += 1

        logger.info(
            "Declaration delay update complete: %d/%d updated", updated, total
        )
        return {"updated": updated, "total": total}
