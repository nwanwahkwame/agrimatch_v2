"""
Automated model retraining for AgriMatch price forecasts.

Runs weekly via the ingestion scheduler (Sunday 10:00 UTC):
  1. Refresh feature_store with the latest clean_prices (pure SQL, no data transfer)
  2. For each crop/market pair with >= MIN_ROWS, retrain an XGBoost return predictor
  3. Persist trained model bytes to model_store table in PostgreSQL

Storing models in PostgreSQL means they survive Railway container restarts and are
visible to the separate API service on its next startup or periodic reload.
"""

import io
import logging

import numpy as np
from sqlalchemy import text

from db.connection import get_session

logger = logging.getLogger(__name__)

MIN_ROWS = 60  # minimum feature_store rows required to retrain a pair

FEATURE_COLS = [
    "lag_7d", "lag_14d", "lag_30d", "lag_90d",
    "rolling_mean_30d", "rolling_std_30d", "rolling_mean_90d",
    "rolling_min_30d", "rolling_max_30d",
    "price_momentum_7d", "price_momentum_30d",
    "sin_week", "cos_week", "sin_month", "cos_month",
    "spi_30day", "et0_mm", "csi_value",
    "fuel_price_diesel", "prev_price",
]

_CREATE_MODEL_STORE = text("""
CREATE TABLE IF NOT EXISTS model_store (
    model_key    TEXT PRIMARY KEY,
    model_bytes  BYTEA NOT NULL,
    mape         FLOAT,
    mae          FLOAT,
    rmse         FLOAT,
    n_train_rows INT,
    trained_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""")

_FEATURE_SQL = text("""
WITH
deduped AS (
    SELECT price_date, market, crop, AVG(price_ghs) AS price_ghs
    FROM clean_prices
    WHERE price_ghs IS NOT NULL
    GROUP BY price_date, market, crop
),
windowed AS (
    SELECT
        d.price_date, d.market, d.crop, d.price_ghs,
        LAG(d.price_ghs,  7) OVER w AS lag_7d,
        LAG(d.price_ghs, 14) OVER w AS lag_14d,
        LAG(d.price_ghs, 30) OVER w AS lag_30d,
        LAG(d.price_ghs, 90) OVER w AS lag_90d,
        AVG(d.price_ghs)    OVER w30 AS rolling_mean_30d,
        STDDEV(d.price_ghs) OVER w30 AS rolling_std_30d,
        AVG(d.price_ghs)    OVER w90 AS rolling_mean_90d,
        MIN(d.price_ghs)    OVER w30 AS rolling_min_30d,
        MAX(d.price_ghs)    OVER w30 AS rolling_max_30d,
        EXTRACT(WEEK  FROM d.price_date)::NUMERIC AS week_num,
        EXTRACT(MONTH FROM d.price_date)::NUMERIC AS month_num,
        gm.district_id
    FROM deduped d
    LEFT JOIN ghana_markets gm ON gm.canonical_name = d.market
    WINDOW
        w   AS (PARTITION BY d.crop, d.market ORDER BY d.price_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
        w30 AS (PARTITION BY d.crop, d.market ORDER BY d.price_date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW),
        w90 AS (PARTITION BY d.crop, d.market ORDER BY d.price_date
                ROWS BETWEEN 89 PRECEDING AND CURRENT ROW)
),
enriched AS (
    SELECT *,
        CASE WHEN lag_7d  IS NOT NULL AND lag_7d  <> 0
             THEN (price_ghs - lag_7d)  / lag_7d  END AS price_momentum_7d,
        CASE WHEN lag_30d IS NOT NULL AND lag_30d <> 0
             THEN (price_ghs - lag_30d) / lag_30d END AS price_momentum_30d,
        SIN(2 * PI() * week_num  / 52) AS sin_week,
        COS(2 * PI() * week_num  / 52) AS cos_week,
        SIN(2 * PI() * month_num / 12) AS sin_month,
        COS(2 * PI() * month_num / 12) AS cos_month
    FROM windowed
    WHERE NOT (lag_7d IS NULL AND lag_14d IS NULL
               AND lag_30d IS NULL AND lag_90d IS NULL)
)
INSERT INTO feature_store (
    feature_date, market, crop, price_ghs,
    lag_7d, lag_14d, lag_30d, lag_90d,
    rolling_mean_30d, rolling_std_30d, rolling_mean_90d,
    rolling_min_30d,  rolling_max_30d,
    price_momentum_7d, price_momentum_30d,
    sin_week, cos_week, sin_month, cos_month,
    spi_30day, et0_mm, csi_value,
    fuel_price_diesel, district_id
)
SELECT
    e.price_date AS feature_date, e.market, e.crop, e.price_ghs,
    e.lag_7d, e.lag_14d, e.lag_30d, e.lag_90d,
    e.rolling_mean_30d, e.rolling_std_30d, e.rolling_mean_90d,
    e.rolling_min_30d,  e.rolling_max_30d,
    e.price_momentum_7d, e.price_momentum_30d,
    e.sin_week, e.cos_week, e.sin_month, e.cos_month,
    ci.spi_30day,
    ci.et0_mm,
    CASE e.crop
        WHEN 'maize'    THEN ci.csi_maize
        WHEN 'tomato'   THEN ci.csi_tomato
        WHEN 'onion'    THEN ci.csi_onion
        WHEN 'cassava'  THEN ci.csi_cassava
        WHEN 'rice'     THEN ci.csi_rice
        WHEN 'plantain' THEN ci.csi_plantain
        ELSE NULL
    END AS csi_value,
    fp.price_ghs_per_litre AS fuel_price_diesel,
    e.district_id
FROM enriched e
LEFT JOIN LATERAL (
    SELECT spi_30day, et0_mm,
           csi_maize, csi_tomato, csi_onion,
           csi_cassava, csi_rice, csi_plantain
    FROM climate_indicators
    WHERE district_id = e.district_id
      AND indicator_date <= e.price_date
    ORDER BY indicator_date DESC LIMIT 1
) ci ON TRUE
LEFT JOIN LATERAL (
    SELECT price_ghs_per_litre
    FROM fuel_prices
    WHERE fuel_type = 'diesel'
      AND price_date <= e.price_date
    ORDER BY price_date DESC LIMIT 1
) fp ON TRUE
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
""")


# ── Feature store refresh ─────────────────────────────────────────────────────

def refresh_feature_store() -> dict:
    """Upsert feature_store from the latest clean_prices.

    Runs entirely on the DB server via window functions and LATERAL joins.
    Safe to call repeatedly; ON CONFLICT DO UPDATE keeps all rows current.
    """
    with get_session() as session:
        result = session.execute(_FEATURE_SQL)
        rows = max(result.rowcount, 0)
    logger.info("Feature store refreshed: %d rows upserted", rows)
    return {"rows_upserted": rows}


# ── Per-pair training ─────────────────────────────────────────────────────────

def _fetch_pair_data(crop: str, market: str):
    """Return (X, y) arrays for one crop/market pair, or (None, None).

    X shape: (n_samples, len(FEATURE_COLS))
    y: 1-step return = (price_t - price_{t-1}) / price_{t-1}
    Rows with |return| > 0.5 are clipped as data errors.
    """
    with get_session() as session:
        rows = session.execute(
            text("""
                SELECT
                    price_ghs,
                    lag_7d, lag_14d, lag_30d, lag_90d,
                    rolling_mean_30d, rolling_std_30d, rolling_mean_90d,
                    rolling_min_30d, rolling_max_30d,
                    price_momentum_7d, price_momentum_30d,
                    sin_week, cos_week, sin_month, cos_month,
                    spi_30day, et0_mm, csi_value, fuel_price_diesel
                FROM feature_store
                WHERE crop = :crop AND market = :market
                ORDER BY feature_date ASC
            """),
            {"crop": crop, "market": market},
        ).fetchall()

    if len(rows) < MIN_ROWS:
        return None, None

    prices = np.array([float(r[0] or 0.0) for r in rows])

    X_list, y_list = [], []
    for i in range(1, len(rows)):
        prev = prices[i - 1]
        if prev <= 0:
            continue
        ret = (prices[i] - prev) / prev
        if abs(ret) > 0.5:
            continue
        row = rows[i]
        # Order matches FEATURE_COLS exactly
        feats = [
            float(row[1]  or 0.0),  # lag_7d
            float(row[2]  or 0.0),  # lag_14d
            float(row[3]  or 0.0),  # lag_30d
            float(row[4]  or 0.0),  # lag_90d
            float(row[5]  or 0.0),  # rolling_mean_30d
            float(row[6]  or 0.0),  # rolling_std_30d
            float(row[7]  or 0.0),  # rolling_mean_90d
            float(row[8]  or 0.0),  # rolling_min_30d
            float(row[9]  or 0.0),  # rolling_max_30d
            float(row[10] or 0.0),  # price_momentum_7d
            float(row[11] or 0.0),  # price_momentum_30d
            float(row[12] or 0.0),  # sin_week
            float(row[13] or 0.0),  # cos_week
            float(row[14] or 0.0),  # sin_month
            float(row[15] or 0.0),  # cos_month
            float(row[16] or 0.0),  # spi_30day
            float(row[17] or 0.0),  # et0_mm
            float(row[18] or 0.0),  # csi_value
            float(row[19] or 0.0),  # fuel_price_diesel
            float(prev),             # prev_price
        ]
        X_list.append(feats)
        y_list.append(ret)

    if len(y_list) < MIN_ROWS:
        return None, None

    return np.array(X_list, dtype=np.float64), np.array(y_list, dtype=np.float64)


def _train_one(crop: str, market: str) -> dict | None:
    """Train and evaluate one XGBoost model. Returns serialised result or None."""
    try:
        from xgboost import XGBRegressor
    except ImportError:
        logger.error("xgboost package not found; cannot retrain")
        return None

    import joblib

    X, y = _fetch_pair_data(crop, market)
    if X is None:
        return None

    n = len(y)
    split = max(int(n * 0.8), n - 30)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    if len(X_train) < 20:
        return None

    model = XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=1,
        verbosity=0,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    if len(X_test) > 0:
        preds  = model.predict(X_test)
        mae    = float(np.mean(np.abs(preds - y_test)))
        rmse   = float(np.sqrt(np.mean((preds - y_test) ** 2)))
        mape   = float(np.mean(np.abs(preds - y_test) / (np.abs(y_test) + 1e-8)))
    else:
        mae = rmse = mape = 0.0

    buf = io.BytesIO()
    joblib.dump(model, buf)

    return {
        "model_key":    f"xgboost/{crop}/{market}",
        "model_bytes":  buf.getvalue(),
        "mape":         mape,
        "mae":          mae,
        "rmse":         rmse,
        "n_train_rows": n,
    }


def _save_to_db(info: dict) -> None:
    with get_session() as session:
        session.execute(
            text("""
                INSERT INTO model_store
                    (model_key, model_bytes, mape, mae, rmse, n_train_rows, trained_at)
                VALUES (:key, :bytes, :mape, :mae, :rmse, :n, NOW())
                ON CONFLICT (model_key) DO UPDATE SET
                    model_bytes  = EXCLUDED.model_bytes,
                    mape         = EXCLUDED.mape,
                    mae          = EXCLUDED.mae,
                    rmse         = EXCLUDED.rmse,
                    n_train_rows = EXCLUDED.n_train_rows,
                    trained_at   = NOW()
            """),
            {
                "key":   info["model_key"],
                "bytes": info["model_bytes"],
                "mape":  info["mape"],
                "mae":   info["mae"],
                "rmse":  info["rmse"],
                "n":     info["n_train_rows"],
            },
        )


# ── Full retraining ───────────────────────────────────────────────────────────

def retrain_xgboost_models() -> dict:
    """Retrain all crop/market pairs and persist updated models to model_store."""
    with get_session() as session:
        pairs = session.execute(
            text("""
                SELECT crop, market, COUNT(*) AS n
                FROM feature_store
                GROUP BY crop, market
                HAVING COUNT(*) >= :min_rows
                ORDER BY crop, market
            """),
            {"min_rows": MIN_ROWS},
        ).fetchall()

    logger.info("Retraining %d crop/market pairs", len(pairs))
    trained = skipped = failed = 0

    for crop, market, n_rows in pairs:
        try:
            result = _train_one(crop, market)
            if result is None:
                skipped += 1
                continue
            _save_to_db(result)
            trained += 1
            logger.info(
                "Trained %s/%s  n=%d  MAPE=%.4f  MAE=%.4f",
                crop, market, result["n_train_rows"],
                result["mape"], result["mae"],
            )
        except Exception as exc:
            failed += 1
            logger.error("Train failed %s/%s: %s", crop, market, exc)

    logger.info("Retrain done. trained=%d skipped=%d failed=%d", trained, skipped, failed)
    return {"trained": trained, "skipped": skipped, "failed": failed, "total_pairs": len(pairs)}


def run_full_retrain() -> dict:
    """Refresh feature_store then retrain all XGBoost models. Called by scheduler."""
    logger.info("=== Full model retrain starting ===")

    # Ensure model_store table exists (idempotent)
    with get_session() as session:
        session.execute(_CREATE_MODEL_STORE)

    feat = refresh_feature_store()
    models = retrain_xgboost_models()

    logger.info("=== Full model retrain complete ===")
    return {"feature_store_rows_upserted": feat["rows_upserted"], **models}
