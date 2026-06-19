"""
M5 feature engineering for AgriMatch.

Transforms clean_prices rows into model-ready features and stores them in
feature_store. All source data is loaded in 4 bulk queries then joined
in-memory, so the total DB round-trips are O(1) not O(pairs).
"""

import math
import logging
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from db.connection import get_session

logger = logging.getLogger(__name__)

_CSI_COLS = {
    "maize":    "csi_maize",
    "tomato":   "csi_tomato",
    "onion":    "csi_onion",
    "cassava":  "csi_cassava",
    "rice":     "csi_rice",
    "plantain": "csi_plantain",
}

_UPSERT_SQL = """
    INSERT INTO feature_store (
        feature_date, market, crop, price_ghs,
        lag_7d, lag_14d, lag_30d, lag_90d,
        rolling_mean_30d, rolling_std_30d, rolling_mean_90d,
        rolling_min_30d, rolling_max_30d,
        price_momentum_7d, price_momentum_30d,
        sin_week, cos_week, sin_month, cos_month,
        spi_30day, et0_mm, csi_value,
        fuel_price_diesel, district_id
    ) VALUES (
        :feature_date, :market, :crop, :price_ghs,
        :lag_7d, :lag_14d, :lag_30d, :lag_90d,
        :rolling_mean_30d, :rolling_std_30d, :rolling_mean_90d,
        :rolling_min_30d, :rolling_max_30d,
        :price_momentum_7d, :price_momentum_30d,
        :sin_week, :cos_week, :sin_month, :cos_month,
        :spi_30day, :et0_mm, :csi_value,
        :fuel_price_diesel, :district_id
    )
    ON CONFLICT (feature_date, market, crop) DO UPDATE SET
        price_ghs          = EXCLUDED.price_ghs,
        lag_7d             = EXCLUDED.lag_7d,
        lag_14d            = EXCLUDED.lag_14d,
        lag_30d            = EXCLUDED.lag_30d,
        lag_90d            = EXCLUDED.lag_90d,
        rolling_mean_30d   = EXCLUDED.rolling_mean_30d,
        rolling_std_30d    = EXCLUDED.rolling_std_30d,
        rolling_mean_90d   = EXCLUDED.rolling_mean_90d,
        rolling_min_30d    = EXCLUDED.rolling_min_30d,
        rolling_max_30d    = EXCLUDED.rolling_max_30d,
        price_momentum_7d  = EXCLUDED.price_momentum_7d,
        price_momentum_30d = EXCLUDED.price_momentum_30d,
        sin_week           = EXCLUDED.sin_week,
        cos_week           = EXCLUDED.cos_week,
        sin_month          = EXCLUDED.sin_month,
        cos_month          = EXCLUDED.cos_month,
        spi_30day          = EXCLUDED.spi_30day,
        et0_mm             = EXCLUDED.et0_mm,
        csi_value          = EXCLUDED.csi_value,
        fuel_price_diesel  = EXCLUDED.fuel_price_diesel,
        district_id        = EXCLUDED.district_id
"""


def _val(v) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return float(v)


class FeatureEngineer:

    # ── Per-series feature computation (operates on in-memory df) ────────────

    def compute_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        s = df["price_ghs"]
        df["lag_7d"]  = s.shift(7)
        df["lag_14d"] = s.shift(14)
        df["lag_30d"] = s.shift(30)
        df["lag_90d"] = s.shift(90)
        return df

    def compute_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        s = df["price_ghs"]
        df["rolling_mean_30d"] = s.rolling(30, min_periods=1).mean()
        df["rolling_std_30d"]  = s.rolling(30, min_periods=2).std()
        df["rolling_mean_90d"] = s.rolling(90, min_periods=1).mean()
        df["rolling_min_30d"]  = s.rolling(30, min_periods=1).min()
        df["rolling_max_30d"]  = s.rolling(30, min_periods=1).max()
        return df

    def compute_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["price_momentum_7d"]  = (df["price_ghs"] - df["lag_7d"])  / df["lag_7d"]
        df["price_momentum_30d"] = (df["price_ghs"] - df["lag_30d"]) / df["lag_30d"]
        df["price_momentum_7d"]  = df["price_momentum_7d"].replace([np.inf, -np.inf], np.nan)
        df["price_momentum_30d"] = df["price_momentum_30d"].replace([np.inf, -np.inf], np.nan)
        return df

    def compute_seasonality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        iso = df.index.isocalendar()
        week_of_year = iso["week"].astype(float).to_numpy()
        month = df.index.month.astype(float)
        df["sin_week"]  = np.sin(2 * math.pi * week_of_year / 52)
        df["cos_week"]  = np.cos(2 * math.pi * week_of_year / 52)
        df["sin_month"] = np.sin(2 * math.pi * month / 12)
        df["cos_month"] = np.cos(2 * math.pi * month / 12)
        return df

    def _join_climate_bulk(
        self,
        df: pd.DataFrame,
        district_id: Optional[int],
        crop: str,
        clim_df: pd.DataFrame,
        climate_districts: set,
    ) -> pd.DataFrame:
        csi_col = _CSI_COLS.get(str(crop).lower())

        did = district_id
        if did is None or did not in climate_districts:
            if not climate_districts:
                df["spi_30day"] = np.nan
                df["et0_mm"]    = np.nan
                df["csi_value"] = np.nan
                return df
            did = min(climate_districts, key=lambda x: abs(x - (district_id or 0)))

        district_clim = (
            clim_df[clim_df["district_id"] == did]
            .sort_values("indicator_date")
            .reset_index(drop=True)
        )

        if district_clim.empty:
            df["spi_30day"] = np.nan
            df["et0_mm"]    = np.nan
            df["csi_value"] = np.nan
            return df

        cols = ["indicator_date", "spi_30day", "et0_mm"]
        if csi_col and csi_col in district_clim.columns:
            sub = district_clim[cols + [csi_col]].rename(columns={csi_col: "csi_value"})
        else:
            sub = district_clim[cols].copy()
            sub["csi_value"] = np.nan

        prices_sorted = df.reset_index().sort_values("price_date")
        merged = pd.merge_asof(
            prices_sorted[["price_date"]],
            sub,
            left_on="price_date",
            right_on="indicator_date",
            direction="backward",
        ).set_index("price_date")

        df["spi_30day"] = merged["spi_30day"]
        df["et0_mm"]    = merged["et0_mm"]
        df["csi_value"] = merged["csi_value"]
        return df

    def _join_fuel_bulk(self, df: pd.DataFrame, fuel_df: pd.DataFrame) -> pd.DataFrame:
        prices_sorted = df.reset_index().sort_values("price_date")
        merged = pd.merge_asof(
            prices_sorted[["price_date"]],
            fuel_df,
            on="price_date",
            direction="backward",
        ).set_index("price_date")
        df["fuel_price_diesel"] = merged["fuel_price_diesel"]
        return df

    # ── Save ──────────────────────────────────────────────────────────────────

    def save_features(
        self,
        df: pd.DataFrame,
        crop: str,
        market: str,
        district_id: Optional[int],
    ) -> int:
        if df.empty:
            return 0
        records = df.reset_index().to_dict("records")
        upserted = 0
        for i in range(0, len(records), 500):
            batch = records[i : i + 500]
            with get_session() as db:
                for row in batch:
                    pd_ts = row["price_date"]
                    fdate = pd_ts.date() if hasattr(pd_ts, "date") else pd_ts
                    db.execute(
                        text(_UPSERT_SQL),
                        {
                            "feature_date":       fdate,
                            "market":             market,
                            "crop":               crop,
                            "price_ghs":          _val(row.get("price_ghs")),
                            "lag_7d":             _val(row.get("lag_7d")),
                            "lag_14d":            _val(row.get("lag_14d")),
                            "lag_30d":            _val(row.get("lag_30d")),
                            "lag_90d":            _val(row.get("lag_90d")),
                            "rolling_mean_30d":   _val(row.get("rolling_mean_30d")),
                            "rolling_std_30d":    _val(row.get("rolling_std_30d")),
                            "rolling_mean_90d":   _val(row.get("rolling_mean_90d")),
                            "rolling_min_30d":    _val(row.get("rolling_min_30d")),
                            "rolling_max_30d":    _val(row.get("rolling_max_30d")),
                            "price_momentum_7d":  _val(row.get("price_momentum_7d")),
                            "price_momentum_30d": _val(row.get("price_momentum_30d")),
                            "sin_week":           _val(row.get("sin_week")),
                            "cos_week":           _val(row.get("cos_week")),
                            "sin_month":          _val(row.get("sin_month")),
                            "cos_month":          _val(row.get("cos_month")),
                            "spi_30day":          _val(row.get("spi_30day")),
                            "et0_mm":             _val(row.get("et0_mm")),
                            "csi_value":          _val(row.get("csi_value")),
                            "fuel_price_diesel":  _val(row.get("fuel_price_diesel")),
                            "district_id":        district_id,
                        },
                    )
            upserted += len(batch)
        return upserted

    # ── Main entry point ──────────────────────────────────────────────────────

    def run_all(self) -> dict:
        """
        Compute features for all (crop, market) pairs via a single SQL query
        that runs entirely on the DB server. Uses window functions + LATERAL
        joins -- no bulk data transfer to Python.
        """
        from setup.run_feature_engineering import FEATURE_SQL
        with get_session() as db:
            result = db.execute(text(FEATURE_SQL))
            rows = result.rowcount
        with get_session() as db:
            pairs = db.execute(text(
                "SELECT COUNT(*) FROM (SELECT DISTINCT crop, market FROM feature_store) x"
            )).scalar()
            total = db.execute(text("SELECT COUNT(*) FROM feature_store")).scalar()
        return {"pairs_ok": pairs, "total_rows": total, "rows_upserted": rows, "failed": []}
