"""
One-time setup: create model_store table and migrate existing .pkl files into it.

Run once against the Railway PostgreSQL database before deploying the worker service:

    $env:DATABASE_URL = "postgresql://..."
    python setup/create_model_store_table.py

After this, the API will load models from the DB on startup, and the weekly retrain
job will update them automatically without needing a redeployment.
"""

import io
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_session
from sqlalchemy import text

DDL = text("""
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


def _parse_stem(stem: str):
    """Parse '{crop}_{market}' stem. Crop names may contain underscores."""
    parts = stem.split("_")
    for i, part in enumerate(parts):
        if part and part[0].isupper():
            return "_".join(parts[:i]), "_".join(parts[i:])
    return None, None


def main():
    print("\n=== model_store setup ===\n")

    # 1. Create table
    print("Step 1: Creating model_store table ...", end=" ", flush=True)
    with get_session() as session:
        session.execute(DDL)
    print("done.")

    # 2. Migrate existing .pkl files
    models_dir = Path(__file__).parent.parent / "models" / "xgboost_returns"
    pkl_files  = sorted(models_dir.glob("*_model.pkl"))
    print(f"\nStep 2: Migrating {len(pkl_files)} .pkl files into model_store ...")

    loaded = skipped = failed = 0
    for pkl_path in pkl_files:
        stem = pkl_path.stem[:-6]   # strip "_model"
        crop, market = _parse_stem(stem)
        if not crop:
            print(f"  [skip] Cannot parse stem: {pkl_path.name}")
            skipped += 1
            continue

        model_key = f"xgboost/{crop}/{market}"

        # Check for existing entry
        with get_session() as session:
            existing = session.execute(
                text("SELECT trained_at FROM model_store WHERE model_key = :k"),
                {"k": model_key},
            ).fetchone()

        if existing:
            print(f"  [skip] {model_key} already in DB (trained {existing[0]})")
            skipped += 1
            continue

        try:
            with open(pkl_path, "rb") as f:
                model_bytes = f.read()

            # Verify the pkl is loadable before inserting
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import joblib
                joblib.load(io.BytesIO(model_bytes))

            with get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO model_store (model_key, model_bytes)
                        VALUES (:key, :bytes)
                        ON CONFLICT (model_key) DO NOTHING
                    """),
                    {"key": model_key, "bytes": model_bytes},
                )

            print(f"  [+] {model_key}  ({len(model_bytes) // 1024} KB)")
            loaded += 1

        except Exception as exc:
            print(f"  [!] {model_key} FAILED: {exc}")
            failed += 1

    print(f"\n=== Done ===")
    print(f"  Migrated : {loaded}")
    print(f"  Skipped  : {skipped}")
    print(f"  Failed   : {failed}")

    # 3. Count
    with get_session() as session:
        total = session.execute(text("SELECT COUNT(*) FROM model_store")).scalar()
    print(f"  Total in DB : {total} models")
    print()


if __name__ == "__main__":
    main()
