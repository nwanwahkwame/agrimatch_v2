"""
M7 - ARIMA and SARIMA baseline price forecasting for AgriMatch.

Loads price series from feature_store, fits ARIMA and SARIMA models
via pmdarima.auto_arima, evaluates on an 80/20 train/test split, and
saves model metadata + 30-day forecasts to the database.
"""

import logging
import math
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
import pmdarima as pm
from pmdarima import ARIMA
from sqlalchemy import select, text

from db.connection import get_session
from db.models import FeatureStore

logger = logging.getLogger(__name__)

_PRIORITY_CROPS = ["maize", "tomato", "onion", "cassava", "rice", "plantain"]
_PRIORITY_MARKETS = ["Kumasi", "Accra", "Tamale", "Techiman", "Bolgatanga"]

_UPSERT_BASELINE = """
    INSERT INTO model_baselines (
        crop, market, model_type,
        order_p, order_d, order_q,
        seasonal_p, seasonal_d, seasonal_q, seasonal_m,
        aic, bic,
        mae_7d, rmse_7d, mae_30d, rmse_30d, mape_7d, mape_30d,
        trained_at, training_rows
    ) VALUES (
        :crop, :market, :model_type,
        :order_p, :order_d, :order_q,
        :seasonal_p, :seasonal_d, :seasonal_q, :seasonal_m,
        :aic, :bic,
        :mae_7d, :rmse_7d, :mae_30d, :rmse_30d, :mape_7d, :mape_30d,
        now(), :training_rows
    )
    ON CONFLICT (crop, market, model_type) DO UPDATE SET
        order_p        = EXCLUDED.order_p,
        order_d        = EXCLUDED.order_d,
        order_q        = EXCLUDED.order_q,
        seasonal_p     = EXCLUDED.seasonal_p,
        seasonal_d     = EXCLUDED.seasonal_d,
        seasonal_q     = EXCLUDED.seasonal_q,
        seasonal_m     = EXCLUDED.seasonal_m,
        aic            = EXCLUDED.aic,
        bic            = EXCLUDED.bic,
        mae_7d         = EXCLUDED.mae_7d,
        rmse_7d        = EXCLUDED.rmse_7d,
        mae_30d        = EXCLUDED.mae_30d,
        rmse_30d       = EXCLUDED.rmse_30d,
        mape_7d        = EXCLUDED.mape_7d,
        mape_30d       = EXCLUDED.mape_30d,
        trained_at     = now(),
        training_rows  = EXCLUDED.training_rows
"""

_UPSERT_FORECAST = """
    INSERT INTO price_forecasts (
        crop, market, model_type,
        forecast_date, horizon_days,
        predicted_price_ghs, lower_bound_ghs, upper_bound_ghs
    ) VALUES (
        :crop, :market, :model_type,
        :forecast_date, :horizon_days,
        :predicted_price_ghs, :lower_bound_ghs, :upper_bound_ghs
    )
    ON CONFLICT (crop, market, model_type, forecast_date, horizon_days) DO UPDATE SET
        predicted_price_ghs = EXCLUDED.predicted_price_ghs,
        lower_bound_ghs     = EXCLUDED.lower_bound_ghs,
        upper_bound_ghs     = EXCLUDED.upper_bound_ghs
"""


def _safe(v) -> Optional[float]:
    """Return None for NaN/inf, float otherwise."""
    try:
        if v is None or math.isnan(float(v)) or math.isinf(float(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


class ARIMABaseline:

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_series(
        self, crop: str, market: str, min_years: int = 3
    ) -> Optional[pd.Series]:
        """Load price_ghs from feature_store, resample to weekly, return if sufficient.

        Returns None when fewer than min_years * 52 observations are available
        after resampling and forward-filling short gaps (up to 8 weeks).
        """
        with get_session() as db:
            rows = db.execute(
                select(FeatureStore.feature_date, FeatureStore.price_ghs)
                .where(
                    FeatureStore.crop == crop,
                    FeatureStore.market == market,
                    FeatureStore.price_ghs.isnot(None),
                )
                .order_by(FeatureStore.feature_date)
            ).fetchall()

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=["feature_date", "price_ghs"])
        df["feature_date"] = pd.to_datetime(df["feature_date"])
        df = df.set_index("feature_date").sort_index()
        df["price_ghs"] = df["price_ghs"].astype(float)

        weekly = df["price_ghs"].resample("W").mean()
        # Interpolate internal gaps, back-fill leading NaN, drop trailing NaN
        weekly = weekly.interpolate(method="linear", limit_direction="forward")
        weekly = weekly.bfill().dropna()

        if len(weekly) < min_years * 52:
            return None

        return weekly

    # ── Model fitting ──────────────────────────────────────────────────────────

    def fit_arima(
        self, series: pd.Series, crop: str, market: str
    ) -> Optional[object]:
        """Fit best non-seasonal ARIMA via auto_arima (stepwise AIC search)."""
        try:
            model = pm.auto_arima(
                series.values,
                seasonal=False,
                max_p=3, max_q=3, max_d=2,
                information_criterion="aic",
                error_action="ignore",
                suppress_warnings=True,
                stepwise=True,
            )
            return model
        except Exception as exc:
            logger.warning("ARIMA fit failed for %s/%s: %s", crop, market, exc)
            return None

    def fit_sarima(
        self, series: pd.Series, crop: str, market: str
    ) -> Optional[object]:
        """Fit best SARIMA with weekly seasonality (m=52) via auto_arima."""
        try:
            model = pm.auto_arima(
                series.values,
                seasonal=True,
                m=52,
                max_p=2, max_q=2, max_d=1,
                max_P=1, max_Q=1, max_D=1,
                information_criterion="aic",
                error_action="ignore",
                suppress_warnings=True,
                stepwise=True,
                maxiter=50,
            )
            return model
        except Exception as exc:
            logger.warning("SARIMA fit failed for %s/%s: %s", crop, market, exc)
            return None

    # ── Evaluation ────────────────────────────────────────────────────────────

    def evaluate_model(self, model, series: pd.Series) -> dict:
        """Evaluate on 80/20 train/test split.

        Retrains using the fitted model's identified order on the training set,
        then forecasts the test period. MAE, RMSE, MAPE are computed at 7-step
        (7-week) and 30-step (30-week) horizons from the start of the test set.
        """
        n = len(series)
        split = int(n * 0.8)
        train = series.iloc[:split]
        test = series.iloc[split:]
        n_test = len(test)
        if n_test < 1:
            return {}

        try:
            ar_p, ar_d, ar_q = model.order
            seasonal = model.seasonal_order
            if seasonal and any(s != 0 for s in seasonal[:3]):
                train_model = ARIMA(
                    order=(ar_p, ar_d, ar_q), seasonal_order=seasonal
                )
            else:
                train_model = ARIMA(order=(ar_p, ar_d, ar_q))
            train_model.fit(train.values)
            raw_preds, _ = train_model.predict(
                n_periods=n_test, return_conf_int=True, alpha=0.2
            )
            preds = np.asarray(raw_preds)
        except Exception as exc:
            logger.warning("Model evaluation step failed: %s", exc)
            return {}

        actual = test.values.astype(float)
        metrics = {}
        for label, h in [("7d", 7), ("30d", 30)]:
            k = min(h, n_test)
            a = actual[:k]
            p_arr = preds[:k]
            diff = np.abs(a - p_arr)
            metrics[f"mae_{label}"] = _safe(np.mean(diff))
            metrics[f"rmse_{label}"] = _safe(np.sqrt(np.mean(diff ** 2)))
            nonzero = np.abs(a) > 0.01
            if nonzero.any():
                metrics[f"mape_{label}"] = _safe(
                    np.mean(diff[nonzero] / np.abs(a[nonzero])) * 100
                )
            else:
                metrics[f"mape_{label}"] = None
        return metrics

    # ── Forecasting ───────────────────────────────────────────────────────────

    def generate_forecast(self, model, steps: int = 30) -> pd.DataFrame:
        """Produce a multi-step forecast with 80% confidence intervals.

        Returns DataFrame with columns forecast_date, horizon_days (1..steps),
        predicted_price_ghs, lower_bound_ghs, upper_bound_ghs.
        """
        today = date.today()
        try:
            raw_preds, raw_conf = model.predict(
                n_periods=steps, return_conf_int=True, alpha=0.2
            )
            preds = np.asarray(raw_preds)
            conf = np.asarray(raw_conf)
        except Exception as exc:
            logger.warning("Forecast generation failed: %s", exc)
            return pd.DataFrame()

        rows = [
            {
                "forecast_date": today,
                "horizon_days": i + 1,
                "predicted_price_ghs": _safe(float(preds[i])),
                "lower_bound_ghs": _safe(float(conf[i, 0])),
                "upper_bound_ghs": _safe(float(conf[i, 1])),
            }
            for i in range(steps)
        ]
        return pd.DataFrame(rows)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_model_results(
        self,
        crop: str,
        market: str,
        model_type: str,
        model,
        metrics: dict,
        training_rows: int,
    ) -> None:
        """Upsert model metadata to model_baselines and 30-day forecast to price_forecasts."""
        ar_p, ar_d, ar_q = model.order
        seasonal = model.seasonal_order
        if seasonal and any(s != 0 for s in seasonal[:3]):
            s_p, s_d, s_q, s_m = seasonal
        else:
            s_p = s_d = s_q = s_m = None

        try:
            aic = _safe(model.aic())
            bic = _safe(model.bic())
        except Exception:
            aic = bic = None

        with get_session() as db:
            db.execute(
                text(_UPSERT_BASELINE),
                {
                    "crop": crop,
                    "market": market,
                    "model_type": model_type,
                    "order_p": ar_p, "order_d": ar_d, "order_q": ar_q,
                    "seasonal_p": s_p, "seasonal_d": s_d,
                    "seasonal_q": s_q, "seasonal_m": s_m,
                    "aic": aic,
                    "bic": bic,
                    "mae_7d": metrics.get("mae_7d"),
                    "rmse_7d": metrics.get("rmse_7d"),
                    "mae_30d": metrics.get("mae_30d"),
                    "rmse_30d": metrics.get("rmse_30d"),
                    "mape_7d": metrics.get("mape_7d"),
                    "mape_30d": metrics.get("mape_30d"),
                    "training_rows": training_rows,
                },
            )

        forecast_df = self.generate_forecast(model)
        if forecast_df.empty:
            return

        with get_session() as db:
            for rec in forecast_df.to_dict("records"):
                db.execute(
                    text(_UPSERT_FORECAST),
                    {
                        "crop": crop,
                        "market": market,
                        "model_type": model_type,
                        "forecast_date": rec["forecast_date"],
                        "horizon_days": rec["horizon_days"],
                        "predicted_price_ghs": rec["predicted_price_ghs"],
                        "lower_bound_ghs": rec["lower_bound_ghs"],
                        "upper_bound_ghs": rec["upper_bound_ghs"],
                    },
                )

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(
        self,
        crops: Optional[list] = None,
        markets: Optional[list] = None,
    ) -> list[dict]:
        """Fit ARIMA and SARIMA for each crop-market pair. Return metrics table.

        Skips pairs with insufficient data (< 3 years of weekly observations).
        Catches and logs fitting errors so one failure does not abort the run.
        """
        if crops is None:
            crops = _PRIORITY_CROPS
        if markets is None:
            markets = _PRIORITY_MARKETS

        results = []

        for crop in crops:
            for market in markets:
                series = self.load_series(crop, market)
                if series is None:
                    print(f"  {crop}/{market}: insufficient data, skipping")
                    continue

                n_obs = len(series)
                row: dict = {"crop": crop, "market": market, "obs": n_obs}

                # -- ARIMA
                print(f"  {crop}/{market} ({n_obs} obs): fitting ARIMA...", flush=True)
                arima = self.fit_arima(series, crop, market)
                if arima is not None:
                    arima_m = self.evaluate_model(arima, series)
                    self.save_model_results(crop, market, "arima", arima, arima_m, n_obs)
                    row["arima_order"] = str(arima.order)
                    row.update({f"arima_{k}": v for k, v in arima_m.items()})
                    arima_label = (
                        f"MAE={arima_m.get('mae_7d', 0):.4f} "
                        f"MAPE={arima_m.get('mape_7d', 0):.2f}%"
                        if arima_m else "no metrics"
                    )
                else:
                    arima_label = "FAILED"

                # -- SARIMA
                print(f"  {crop}/{market} ({n_obs} obs): fitting SARIMA (m=52)...", flush=True)
                sarima = self.fit_sarima(series, crop, market)
                if sarima is not None:
                    sarima_m = self.evaluate_model(sarima, series)
                    self.save_model_results(crop, market, "sarima", sarima, sarima_m, n_obs)
                    row["sarima_order"] = str(sarima.order)
                    row.update({f"sarima_{k}": v for k, v in sarima_m.items()})
                    sarima_label = (
                        f"MAE={sarima_m.get('mae_7d', 0):.4f} "
                        f"MAPE={sarima_m.get('mape_7d', 0):.2f}%"
                        if sarima_m else "no metrics"
                    )
                else:
                    sarima_label = "FAILED"

                print(
                    f"  {crop}/{market}: "
                    f"ARIMA {arima_label} | SARIMA {sarima_label}"
                )
                results.append(row)

        return results
