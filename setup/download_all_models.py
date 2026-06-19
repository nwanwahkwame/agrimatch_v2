"""
Model setup script for AgriMatch.

Place the following zip files in the downloads/ folder at the project root,
then run this script:

    downloads/xgboost_returns.zip   -> models/xgboost_returns/
    downloads/lstm_models_recent.zip -> models/lstm_recent/
    downloads/m11_models.zip         -> models/m11/

Usage (from project root):
    python setup/download_all_models.py
"""

import sys
import zipfile
from pathlib import Path

ROOT      = Path(__file__).parent.parent
DOWNLOADS = ROOT / "downloads"

ZIPS = {
    "xgboost_returns": {
        "zip":    DOWNLOADS / "xgboost_returns.zip",
        "dest":   ROOT / "models" / "xgboost_returns",
        "checks": {
            "pkl_glob":  "*_model.pkl",
            "required":  ["feature_columns.json", "model_config.json"],
        },
    },
    "lstm_recent": {
        "zip":    DOWNLOADS / "lstm_models_recent.zip",
        "dest":   ROOT / "models" / "lstm_recent",
        "checks": {
            "keras_glob": "*_model.keras",
            "required":   ["feature_columns.json", "model_config.json"],
        },
    },
    "m11": {
        "zip":    DOWNLOADS / "m11_models.zip",
        "dest":   ROOT / "models" / "m11",
        "checks": {
            "required": [
                "harvest_delay_classifier.pkl",
                "feature_columns.json",
                "model_config.json",
            ],
        },
    },
}


def _already_populated(name: str, cfg: dict) -> bool:
    """Return True if the destination folder already has the expected files."""
    dest   = cfg["dest"]
    checks = cfg["checks"]

    if not dest.exists():
        return False

    for fname in checks.get("required", []):
        if not (dest / fname).exists():
            return False

    if "pkl_glob" in checks and not list(dest.glob(checks["pkl_glob"])):
        return False

    if "keras_glob" in checks and not list(dest.glob(checks["keras_glob"])):
        return False

    return True


def _unzip(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members   = zf.infolist()
        total     = len(members)
        interval  = max(1, total // 10)
        for i, member in enumerate(members, 1):
            zf.extract(member, dest)
            if i % interval == 0 or i == total:
                pct = i / total * 100
                print(f"    {pct:5.1f}%  ({i}/{total} files)", flush=True)


def main():
    print()
    print("=" * 60)
    print("AgriMatch Model Setup")
    print("=" * 60)

    DOWNLOADS.mkdir(exist_ok=True)

    missing_zips = []
    skipped      = []
    extracted    = []
    errors       = []

    for name, cfg in ZIPS.items():
        zip_path = cfg["zip"]
        dest     = cfg["dest"]

        # Already good — skip
        if _already_populated(name, cfg):
            skipped.append(name)
            print(f"\n  [{name}] already populated — skipping unzip.")
            continue

        # Zip missing
        if not zip_path.exists():
            missing_zips.append(name)
            print(f"\n  [{name}] zip not found: {zip_path.name}")
            continue

        # Unzip
        print(f"\n  [{name}] Unzipping {zip_path.name} -> {dest.relative_to(ROOT)} ...")
        try:
            _unzip(zip_path, dest)
            extracted.append(name)
            print(f"    Done.")
        except Exception as exc:
            errors.append((name, str(exc)))
            print(f"    ERROR: {exc}")

    # ── Verify ────────────────────────────────────────────────────────────────
    print()
    print("-" * 60)
    print("Verification")
    print("-" * 60)

    xgb_dest  = ZIPS["xgboost_returns"]["dest"]
    lstm_dest = ZIPS["lstm_recent"]["dest"]
    m11_dest  = ZIPS["m11"]["dest"]

    xgb_models  = list(xgb_dest.glob("*_model.pkl"))  if xgb_dest.exists()  else []
    lstm_models = list(lstm_dest.glob("*_model.keras")) if lstm_dest.exists() else []
    m11_clf     = (m11_dest / "harvest_delay_classifier.pkl").exists() if m11_dest.exists() else False

    all_ready = (
        len(xgb_models)  > 0
        and len(lstm_models) > 0
        and m11_clf
        and not errors
    )

    print(f"  XGBoost models found  : {len(xgb_models)}")
    print(f"  LSTM models found     : {len(lstm_models)}")
    print(f"  M11 classifier found  : {'yes' if m11_clf else 'no'}")
    print(f"  All models ready      : {'yes' if all_ready else 'no'}")

    # ── Missing zip instructions ───────────────────────────────────────────────
    if missing_zips:
        print()
        print("-" * 60)
        print("Missing zips — action needed")
        print("-" * 60)
        zip_names = {
            "xgboost_returns": "xgboost_returns.zip",
            "lstm_recent":     "lstm_models_recent.zip",
            "m11":             "m11_models.zip",
        }
        for name in missing_zips:
            print(f"  {zip_names[name]}")
        print()
        print(f"  Place the missing files in:")
        print(f"    {DOWNLOADS}")
        print()
        print("  Then re-run:  python setup/download_all_models.py")

    if errors:
        print()
        print("-" * 60)
        print("Errors")
        print("-" * 60)
        for name, msg in errors:
            print(f"  [{name}] {msg}")

    print()
    print("=" * 60)
    return 0 if all_ready else 1


if __name__ == "__main__":
    sys.exit(main())
