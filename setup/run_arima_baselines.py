"""
Create model_baselines and price_forecasts tables, then run
ARIMABaseline for all priority crop-market pairs.

Prints:
  - Model performance table sorted by MAPE
  - Best model per crop (lowest MAPE_7d)
  - Worst performing crop-market pair
  - Sample 30-day forecast for maize/Kumasi

Usage (from project root):
    python setup/run_arima_baselines.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

# ── DDL ───────────────────────────────────────────────────────────────────────

DDL = [
    """
    CREATE TABLE IF NOT EXISTS model_baselines (
        id             BIGSERIAL PRIMARY KEY,
        crop           TEXT NOT NULL,
        market         TEXT NOT NULL,
        model_type     TEXT NOT NULL,
        order_p        INTEGER,
        order_d        INTEGER,
        order_q        INTEGER,
        seasonal_p     INTEGER,
        seasonal_d     INTEGER,
        seasonal_q     INTEGER,
        seasonal_m     INTEGER,
        aic            NUMERIC(12,4),
        bic            NUMERIC(12,4),
        mae_7d         NUMERIC(10,4),
        rmse_7d        NUMERIC(10,4),
        mae_30d        NUMERIC(10,4),
        rmse_30d       NUMERIC(10,4),
        mape_7d        NUMERIC(10,4),
        mape_30d       NUMERIC(10,4),
        trained_at     TIMESTAMPTZ DEFAULT now(),
        training_rows  INTEGER,
        CONSTRAINT uq_model_baselines_crop_market_type
            UNIQUE (crop, market, model_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_forecasts (
        id                   BIGSERIAL PRIMARY KEY,
        crop                 TEXT NOT NULL,
        market               TEXT NOT NULL,
        model_type           TEXT NOT NULL,
        forecast_date        DATE NOT NULL,
        horizon_days         INTEGER,
        predicted_price_ghs  NUMERIC(10,2),
        lower_bound_ghs      NUMERIC(10,2),
        upper_bound_ghs      NUMERIC(10,2),
        actual_price_ghs     NUMERIC(10,2),
        created_at           TIMESTAMPTZ DEFAULT now(),
        CONSTRAINT uq_price_forecast_key
            UNIQUE (crop, market, model_type, forecast_date, horizon_days)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_price_forecasts_crop_market_date
        ON price_forecasts (crop, market, forecast_date)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_model_baselines_crop_market
        ON model_baselines (crop, market)
    """,
]


def _fmt(v, decimals=4) -> str:
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print()
    print("Step 1: Creating model_baselines and price_forecasts tables ...")
    with conn.cursor() as cur:
        for stmt in DDL:
            cur.execute(stmt)
    conn.commit()
    print("  Done.")
    conn.close()

    print()
    print("Step 2: Running ARIMA/SARIMA baseline fitting ...")
    print("  (This may take several minutes for SARIMA with m=52)")
    print()

    from models.arima_baseline import ARIMABaseline
    baseline = ARIMABaseline()
    results = baseline.run()

    if not results:
        print("No crop-market pairs had sufficient data.")
        return

    print()
    print("=" * 70)
    print("MODEL PERFORMANCE (sorted by ARIMA MAPE_7d)")
    print("=" * 70)
    print(
        f"  {'Crop':<10} {'Market':<12} {'Type':<8} "
        f"{'MAE_7d':>8} {'RMSE_7d':>8} {'MAPE_7d':>8} {'Order':<20}"
    )
    print("  " + "-" * 68)

    # Flatten to one row per (crop, market, model_type)
    flat = []
    for row in results:
        for mtype in ("arima", "sarima"):
            mape = row.get(f"{mtype}_mape_7d")
            if mape is not None:
                flat.append({
                    "crop": row["crop"],
                    "market": row["market"],
                    "model_type": mtype,
                    "mae_7d": row.get(f"{mtype}_mae_7d"),
                    "rmse_7d": row.get(f"{mtype}_rmse_7d"),
                    "mape_7d": mape,
                    "order": row.get(f"{mtype}_order", ""),
                })

    flat.sort(key=lambda r: (r.get("mape_7d") or 9999))

    for r in flat:
        print(
            f"  {r['crop']:<10} {r['market']:<12} {r['model_type']:<8} "
            f"{_fmt(r['mae_7d']):>8} {_fmt(r['rmse_7d']):>8} "
            f"{_fmt(r['mape_7d']):>7}% {r['order']:<20}"
        )

    # Best model per crop
    print()
    print("Best model per crop (lowest MAPE_7d):")
    print("  " + "-" * 50)
    by_crop: dict = {}
    for r in flat:
        crop = r["crop"]
        mape = r.get("mape_7d") or 9999
        if crop not in by_crop or mape < by_crop[crop]["mape_7d"]:
            by_crop[crop] = r
    for crop, r in sorted(by_crop.items()):
        print(
            f"  {crop:<12} {r['model_type'].upper():<8} "
            f"({r['market']})  MAPE={_fmt(r['mape_7d'])}%"
        )

    # Worst pair
    if flat:
        worst = max(flat, key=lambda r: r.get("mape_7d") or 0)
        print()
        print(
            f"Worst pair: {worst['crop']}/{worst['market']} "
            f"{worst['model_type'].upper()}  MAPE={_fmt(worst['mape_7d'])}%"
        )

    # Sample 30-day forecast for maize/Kumasi
    print()
    print("Sample 30-day forecast for maize/Kumasi")
    print("  (showing horizon 1, 7, 14, 21, 30)")
    print("  " + "-" * 50)

    from dotenv import load_dotenv as _ld
    _ld(Path(__file__).parent.parent / ".env")
    from db.connection import get_session
    from sqlalchemy import text as _text
    from datetime import date

    with get_session() as db:
        rows = db.execute(
            _text("""
                SELECT model_type, horizon_days, predicted_price_ghs,
                       lower_bound_ghs, upper_bound_ghs
                FROM price_forecasts
                WHERE crop = 'maize' AND market = 'Kumasi'
                  AND forecast_date = :dt
                ORDER BY model_type, horizon_days
            """),
            {"dt": date.today()},
        ).fetchall()

    if rows:
        show_horizons = {1, 7, 14, 21, 30}
        current_type = None
        for mtype, horizon, pred, lo, hi in rows:
            if horizon not in show_horizons:
                continue
            if mtype != current_type:
                print(f"  [{mtype.upper()}]")
                current_type = mtype
            print(
                f"    Day {horizon:>2}: {_fmt(pred, 2)} GHS "
                f"[{_fmt(lo, 2)} - {_fmt(hi, 2)}]"
            )
    else:
        print("  (no maize/Kumasi forecasts -- pair may have had insufficient data)")

    print()
    print(f"Total pairs fitted: {len(results)}")
    print(f"Total model rows saved: {len(flat)}")
    print()


if __name__ == "__main__":
    main()
