"""
LSTM encoder-decoder price predictor for AgriMatch.

Models predict 3-step (monthly) price forecasts using a 24-step lookback.
Models live in models/lstm_recent/.
"""

import json
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Optional

_COL_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

import joblib
import numpy as np
from sqlalchemy import text

from db.connection import get_session

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

logger = logging.getLogger(__name__)

_MODELS_DIR        = Path(__file__).parent / "lstm_recent"
_FEATURE_COLS_PATH = _MODELS_DIR / "feature_columns.json"
_CONFIG_PATH       = _MODELS_DIR / "model_config.json"

_HORIZON_DAYS = [30, 60, 90]


class LSTMPredictor:

    def __init__(self):
        self.models: dict       = {}
        self.scalers: dict      = {}
        self.feature_cols: list = []
        self.config: dict       = {}
        self.lookback: int      = 24
        self.n_features: int    = 15
        self.target_idx: int    = 0

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_models(self) -> int:
        """Scan models/lstm_recent/ for *_model.keras and load each with its scaler."""
        with open(_CONFIG_PATH) as f:
            self.config = json.load(f)
        self.lookback   = self.config.get("lookback", 24)
        self.n_features = self.config.get("n_features", 15)
        self.target_idx = self.config.get("target_idx", 0)

        with open(_FEATURE_COLS_PATH) as f:
            self.feature_cols = json.load(f)

        import keras  # deferred — avoids TF startup cost when predictor not used
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for model_path in sorted(_MODELS_DIR.glob("*_model.keras")):
                bare  = model_path.stem[:-6]          # strip "_model"
                crop, market = bare.split("_", 1)
                key = f"{crop}/{market}"
                try:
                    self.models[key] = keras.models.load_model(
                        model_path, compile=False
                    )
                except Exception as exc:
                    logger.warning("Failed to load %s: %s", model_path.name, exc)
                    continue
                scaler_path = (
                    model_path.parent
                    / model_path.name.replace("_model.keras", "_scaler.pkl")
                )
                try:
                    self.scalers[key] = joblib.load(scaler_path)
                except Exception as exc:
                    logger.warning("Failed to load scaler for %s: %s", key, exc)

        n = len(self.models)
        logger.info("Loaded %d LSTM models", n)
        return n

    # ── Sequence fetch ────────────────────────────────────────────────────────

    def get_sequence(
        self, crop: str, market: str
    ) -> Optional[tuple[np.ndarray, str]]:
        """Return (arr, latest_feature_date) for crop/market.

        arr shape: (lookback, n_features), oldest-to-newest.
        Nulls are forward-filled then median-filled.
        Returns None if fewer than lookback rows exist.
        """
        if not all(_COL_PATTERN.match(c) for c in self.feature_cols):
            raise ValueError("Invalid feature column names detected in feature_columns.json")
        cols_sql = ", ".join(self.feature_cols)
        with get_session() as db:
            rows = db.execute(
                text(f"""
                    SELECT {cols_sql}, feature_date
                    FROM feature_store
                    WHERE crop   = :crop
                      AND market = :market
                    ORDER BY feature_date DESC
                    LIMIT :n
                """),
                {"crop": crop, "market": market, "n": self.lookback},
            ).fetchall()

        if len(rows) < self.lookback:
            return None

        # rows[0] is most recent; reverse to chronological
        rows = list(reversed(rows))
        latest_date = str(rows[-1][-1])  # feature_date of most recent row

        arr = np.array(
            [
                [
                    float(getattr(row, col)) if getattr(row, col) is not None else np.nan
                    for col in self.feature_cols
                ]
                for row in rows
            ],
            dtype=np.float64,
        )

        # Forward fill (time axis)
        for c in range(arr.shape[1]):
            col_vals = arr[:, c]
            mask = np.isnan(col_vals)
            if mask.any():
                idx = np.where(~mask, np.arange(len(mask)), 0)
                np.maximum.accumulate(idx, out=idx)
                arr[:, c] = col_vals[idx]

        # Fill any remaining NaNs (leading) with column median
        for c in range(arr.shape[1]):
            mask = np.isnan(arr[:, c])
            if mask.any():
                vals = arr[~mask, c]
                arr[mask, c] = np.median(vals) if len(vals) > 0 else 0.0

        return arr, latest_date

    # ── Core prediction ───────────────────────────────────────────────────────

    def predict(self, crop: str, market: str) -> Optional[dict]:
        """Return 30/60/90-day LSTM forecasts for crop/market.

        Falls back to a same-crop model if exact pair is missing.
        """
        result = self.get_sequence(crop, market)
        if result is None:
            logger.warning(
                "Fewer than %d feature_store rows for %s/%s",
                self.lookback, crop, market,
            )
            return None

        seq, feature_date = result
        last_known_price  = float(seq[-1, self.target_idx])

        try:
            std_idx     = self.feature_cols.index("rolling_std_30d")
            rolling_std = float(seq[-1, std_idx])
        except (ValueError, IndexError):
            rolling_std = 0.0
        if rolling_std <= 0.0:
            rolling_std = last_known_price * 0.10

        # Model lookup with same-crop fallback
        key      = f"{crop}/{market}"
        model    = self.models.get(key)
        scaler   = self.scalers.get(key)
        fallback = False

        if model is None:
            same_crop = [k for k in self.models if k.startswith(f"{crop}/")]
            if not same_crop:
                logger.warning("No LSTM model found for crop '%s'", crop)
                return None
            key      = same_crop[0]
            model    = self.models[key]
            scaler   = self.scalers.get(key)
            fallback = True
            logger.info("Using LSTM fallback model %s for %s/%s", key, crop, market)

        # Scale sequence and predict
        scaled = scaler.transform(seq)                            # (24, 15)
        x      = scaled.reshape(1, self.lookback, self.n_features)  # (1, 24, 15)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                preds = model.predict(x, verbose=0)              # (1, 3)
        except Exception as exc:
            logger.error("LSTM prediction failed for %s: %s", key, exc)
            return None

        # Inverse-transform each horizon step individually
        dummy     = np.zeros((1, self.n_features))
        forecasts = []
        for i, h_days in enumerate(_HORIZON_DAYS):
            dummy[0, self.target_idx] = float(preds[0, i])
            inv       = scaler.inverse_transform(dummy)
            predicted = max(0.0, float(inv[0, self.target_idx]))
            margin    = 1.5 * rolling_std
            forecasts.append({
                "horizon_days":        h_days,
                "predicted_price_ghs": round(predicted, 2),
                "lower_bound_ghs":     round(max(0.0, predicted - margin), 2),
                "upper_bound_ghs":     round(predicted + margin, 2),
            })

        return {
            "crop":             crop,
            "market":           market,
            "model_type":       "lstm",
            "model_key":        key,
            "fallback_model":   fallback,
            "last_known_price": round(last_known_price, 2),
            "feature_date":     feature_date,
            "forecasts":        forecasts,
        }
