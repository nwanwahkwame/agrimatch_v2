"""
XGBoost return-based price predictor for AgriMatch.

Models predict price RETURNS (fractional change), not absolute prices.
Final price: prev_price * (1 + predicted_return)

Models live in models/xgboost_returns/.
"""

import csv
import io
import json
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sqlalchemy import text

from db.connection import get_session

logger = logging.getLogger(__name__)

_MODELS_DIR        = Path(__file__).parent / "xgboost_returns"
_FEATURE_COLS_PATH = _MODELS_DIR / "feature_columns.json"
_METRICS_PATH      = _MODELS_DIR / "model_metrics.csv"

_HORIZON_DAYS         = {1: 30, 2: 60, 3: 90}
_HORIZON_RETURN_DECAY = {1: 1.0, 2: 0.9, 3: 0.8}
_STABLE_BAND          = 0.02   # within 2% of last_known_price -> "stable"


def _parse_stem(stem: str) -> tuple[str, str]:
    """Parse '{crop}_{market}' stem into (crop, market).

    Crop names may contain underscores (fish_mackerel, garden_egg).
    Market names always start with an uppercase letter.
    """
    parts = stem.split("_")
    for i, part in enumerate(parts):
        if part and part[0].isupper():
            return "_".join(parts[:i]), "_".join(parts[i:])
    raise ValueError(f"Cannot parse crop/market from stem: {stem!r}")


def _direction(predicted: float, reference: float) -> str:
    if reference <= 0:
        return "stable"
    change = (predicted - reference) / reference
    if change > _STABLE_BAND:
        return "up"
    if change < -_STABLE_BAND:
        return "down"
    return "stable"


class XGBoostPredictor:

    def __init__(self):
        self.models: dict            = {}
        self.feature_cols: list      = []
        self.metrics: dict           = {}   # key: "crop/market" -> {mae, rmse, mape}
        self._db_latest_trained_at: Optional[datetime] = None  # timestamp of newest DB model

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load_feature_cols(self) -> None:
        """Load feature column list and metrics CSV from filesystem."""
        with open(_FEATURE_COLS_PATH) as f:
            self.feature_cols = json.load(f)

        if _METRICS_PATH.exists():
            with open(_METRICS_PATH, newline="") as f:
                for row in csv.DictReader(f):
                    self.metrics[row["pair"]] = {
                        "mae":  float(row["mae"]),
                        "rmse": float(row["rmse"]),
                        "mape": float(row["mape"]),
                    }

    def load_from_db(self) -> int:
        """Load models from model_store table in PostgreSQL.

        Returns count loaded, or 0 if the table does not exist or is empty.
        Called by load_models() before falling back to .pkl files on disk.
        After the weekly retrain job runs, the API picks up fresh models on its
        next reload without requiring a redeploy.
        """
        try:
            with get_session() as db:
                rows = db.execute(
                    text("""
                        SELECT model_key, model_bytes, mape, mae, rmse, trained_at
                        FROM model_store
                    """)
                ).fetchall()
        except Exception as exc:
            logger.debug("model_store not available: %s", exc)
            return 0

        if not rows:
            return 0

        self._load_feature_cols()
        loaded = 0
        latest_ts: Optional[datetime] = None

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for row in rows:
                model_key   = row[0]
                model_bytes = row[1]
                mape        = row[2]
                mae         = row[3]
                rmse        = row[4]
                trained_at  = row[5]

                # model_key format: "xgboost/{crop}/{market}"
                parts = model_key.split("/", 2)
                if len(parts) != 3 or parts[0] != "xgboost":
                    continue

                try:
                    model = joblib.load(io.BytesIO(bytes(model_bytes)))
                    self.models[f"{parts[1]}/{parts[2]}"] = model
                    if mape is not None:
                        self.metrics[f"{parts[1]}/{parts[2]}"] = {
                            "mae":  float(mae  or 0.0),
                            "rmse": float(rmse or 0.0),
                            "mape": float(mape),
                        }
                    if trained_at and (latest_ts is None or trained_at > latest_ts):
                        latest_ts = trained_at
                    loaded += 1
                except Exception as exc:
                    logger.warning("Failed to load DB model %s: %s", model_key, exc)

        self._db_latest_trained_at = latest_ts
        logger.info("Loaded %d XGBoost models from model_store (DB)", loaded)
        return loaded

    def _load_from_filesystem(self) -> int:
        """Load models from models/xgboost_returns/*.pkl files (original behaviour)."""
        self._load_feature_cols()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for model_path in sorted(_MODELS_DIR.glob("*_model.pkl")):
                stem = model_path.stem[:-6]   # strip "_model"
                try:
                    crop, market = _parse_stem(stem)
                except ValueError as exc:
                    logger.warning("Skipping %s: %s", model_path.name, exc)
                    continue
                key = f"{crop}/{market}"
                try:
                    self.models[key] = joblib.load(model_path)
                except Exception as exc:
                    logger.warning("Failed to load %s: %s", model_path.name, exc)

        return len(self.models)

    def load_models(self) -> int:
        """Load XGBoost models: tries model_store DB first, falls back to .pkl files.

        DB models are preferred because they are kept current by the weekly retrain
        job running in the worker service on Railway.  Filesystem .pkl files are
        used as the baseline when no DB models exist yet (fresh deployment).
        """
        n_db = self.load_from_db()
        if n_db > 0:
            print(f"Loaded {n_db} XGBoost models from DB (model_store)", flush=True)
            return n_db

        n_fs = self._load_from_filesystem()
        print(f"Loaded {n_fs} XGBoost models from filesystem (.pkl)", flush=True)
        return n_fs

    def maybe_reload_from_db(self) -> bool:
        """Reload all models from DB if the worker has trained newer ones since startup.

        Called by the API's hourly scheduler job so fresh models are picked up
        without restarting the web service.  Returns True if a reload happened.
        """
        try:
            with get_session() as db:
                latest = db.execute(
                    text("SELECT MAX(trained_at) FROM model_store")
                ).scalar()
        except Exception:
            return False

        if latest is None:
            return False

        # Normalise to UTC-aware for comparison
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)

        if (
            self._db_latest_trained_at is None
            or latest > self._db_latest_trained_at
        ):
            self.models.clear()
            self.metrics.clear()
            n = self.load_from_db()
            if n > 0:
                logger.info("Model hot-reload: %d models updated from DB", n)
                return True
        return False

    # ── Feature fetch ─────────────────────────────────────────────────────────

    def get_features(
        self, crop: str, market: str
    ) -> tuple[Optional[dict], Optional[dict]]:
        """Return (latest_row, previous_row) feature dicts for crop/market.

        Both dicts include all feature_cols plus 'price_ghs' and 'feature_date'.
        Returns (None, None) if fewer than 2 rows exist.
        """
        with get_session() as db:
            rows = db.execute(
                text("""
                    SELECT *
                    FROM feature_store
                    WHERE crop   = :crop
                      AND market = :market
                    ORDER BY feature_date DESC
                    LIMIT 2
                """),
                {"crop": crop, "market": market},
            ).fetchall()

        if len(rows) < 2:
            return None, None

        def _row_to_dict(row) -> dict:
            d = {col: getattr(row, col, None) for col in self.feature_cols}
            d["price_ghs"]    = getattr(row, "price_ghs", None)
            d["feature_date"] = getattr(row, "feature_date", None)
            return d

        return _row_to_dict(rows[0]), _row_to_dict(rows[1])

    # ── Core prediction ───────────────────────────────────────────────────────

    def predict(
        self,
        crop: str,
        market: str,
        horizons: list[int] = None,
    ) -> Optional[dict]:
        """Predict future prices for crop/market using return-based XGBoost.

        The model predicts price_return; final price = prev_price * (1 + return).
        Multi-step horizons apply the return recursively with slight decay.
        Falls back to the best same-crop model (lowest MAPE) when exact match missing.
        Returns None when no model exists for the crop or features are unavailable.
        """
        if horizons is None:
            horizons = [1, 2, 3]

        latest_row, prev_row = self.get_features(crop, market)
        if latest_row is None:
            logger.warning("Fewer than 2 feature_store rows for %s/%s", crop, market)
            return None

        last_known_price = float(latest_row.get("price_ghs") or 0.0)
        prev_price       = float(prev_row.get("price_ghs") or 0.0)

        # Model lookup with same-crop fallback
        key      = f"{crop}/{market}"
        model    = self.models.get(key)
        fallback = False

        if model is None:
            same_crop = {k: v for k, v in self.metrics.items() if k.startswith(f"{crop}/")}
            if not same_crop:
                logger.warning("No model found for crop '%s'", crop)
                return None
            best_key = min(same_crop, key=lambda k: same_crop[k]["mape"])
            model    = self.models.get(best_key)
            if model is None:
                return None
            key      = best_key
            fallback = True
            logger.info("Using fallback model %s for %s/%s", best_key, crop, market)

        # Build feature vector: 19 standard features from latest_row,
        # then prev_price as the final column (overrides any stored value).
        x = np.array(
            [
                float(latest_row.get(col) or 0.0) if col != "prev_price"
                else prev_price
                for col in self.feature_cols
            ],
            dtype=np.float64,
        ).reshape(1, -1)

        try:
            pred_return = float(model.predict(x)[0])
        except Exception as exc:
            logger.error("Prediction failed for %s: %s", key, exc)
            return None

        # Metrics for confidence
        m          = self.metrics.get(key, {})
        mape       = m.get("mape", 20.0)
        confidence = round(1.0 / (1.0 + mape / 100.0), 4)

        # rolling_std_30d for CI (in GHS; fall back to 10% of last known)
        rolling_std = float(latest_row.get("rolling_std_30d") or 0.0)
        if rolling_std <= 0.0:
            rolling_std = last_known_price * 0.10

        # Multi-step recursive forecast with return decay
        forecast_list = []
        running_price = prev_price
        for h in sorted(horizons):
            decay          = _HORIZON_RETURN_DECAY.get(h, 1.0)
            running_price  = running_price * (1.0 + pred_return * decay)
            predicted      = max(0.0, running_price)
            margin         = 1.5 * rolling_std
            h_days         = _HORIZON_DAYS.get(h, h * 30)
            forecast_list.append({
                "horizon_days":        h_days,
                "predicted_price_ghs": round(predicted, 2),
                "lower_bound_ghs":     round(max(0.0, predicted - margin), 2),
                "upper_bound_ghs":     round(predicted + margin, 2),
                "direction":           _direction(predicted, last_known_price),
            })

        return {
            "crop":             crop,
            "market":           market,
            "model_type":       "xgboost_returns",
            "model_key":        key,
            "fallback_model":   fallback,
            "last_known_price": round(last_known_price, 2),
            "predicted_return": round(pred_return, 6),
            "mape":             round(mape, 4),
            "confidence":       confidence,
            "forecasts":        forecast_list,
            "feature_date":     str(latest_row.get("feature_date")),
        }

    # ── All-market forecast ───────────────────────────────────────────────────

    def get_all_forecasts(self, crop: str) -> list:
        """Return forecasts for all markets that have a model for this crop.

        Sorted by 30-day predicted_price_ghs descending.
        """
        keys    = [k for k in self.models if k.startswith(f"{crop}/")]
        results = []
        for key in keys:
            _, market = key.split("/", 1)
            result = self.predict(crop, market)
            if result is not None:
                results.append(result)

        results.sort(
            key=lambda r: r["forecasts"][0]["predicted_price_ghs"] if r["forecasts"] else 0.0,
            reverse=True,
        )
        return results

    # ── Declaration-level prediction ─────────────────────────────────────────

    def predict_for_declaration(self, declaration_id: int) -> Optional[dict]:
        """Load a declaration and return price forecasts for its crop/market."""
        with get_session() as db:
            decl = db.execute(
                text("""
                    SELECT fd.id, fd.crop, fd.district_id,
                           fd.quantity_kg, fd.harvest_date,
                           f.full_name AS farmer_name
                    FROM farmer_declarations fd
                    JOIN farmers f ON f.id = fd.farmer_id
                    WHERE fd.id = :did
                """),
                {"did": declaration_id},
            ).fetchone()

        if decl is None:
            logger.warning("Declaration %s not found", declaration_id)
            return None

        with get_session() as db:
            dist_row = db.execute(
                text("SELECT name FROM ghana_districts WHERE id = :did LIMIT 1"),
                {"did": decl.district_id},
            ).fetchone()

        with get_session() as db:
            mkt_row = db.execute(
                text("""
                    SELECT canonical_name FROM ghana_markets
                    WHERE district_id = :did LIMIT 1
                """),
                {"did": decl.district_id},
            ).fetchone()

        market = mkt_row[0] if mkt_row else None
        pred   = self.predict(decl.crop, market or "unknown")
        if pred is None:
            return None

        pred["declaration_id"] = declaration_id
        pred["farmer_name"]    = decl.farmer_name
        pred["district"]       = dist_row[0] if dist_row else None
        pred["quantity_kg"]    = float(decl.quantity_kg) if decl.quantity_kg else None
        pred["harvest_date"]   = str(decl.harvest_date)
        return pred
