"""
Manual pipeline trigger for development and testing.

Usage:
    python run_pipeline.py --source hdx
    python run_pipeline.py --source mofa
    python run_pipeline.py --source all
"""

import argparse
import logging
import sys
import time
from typing import Any

from ingestion.scheduler import run_hdx_pipeline, run_mofa_pipeline

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Summary table ─────────────────────────────────────────────────────────────

def _print_summary(results: list[dict[str, Any]]) -> None:
    """Print a fixed-width summary table from a list of pipeline result dicts."""

    # Column definitions: (header, key, width)
    columns = [
        ("Source",      "source",           14),
        ("Fetched",     "rows_fetched",      9),
        ("Clean",       "rows_clean",        9),
        ("Quarantined", "rows_quarantined",  13),
        ("Duplicates",  "rows_duplicate",    12),
        ("Status",      "status",            10),
    ]

    sep   = "+" + "+".join("-" * (w + 2) for _, _, w in columns) + "+"
    header = "|" + "|".join(
        f" {h:<{w}} " for h, _, w in columns
    ) + "|"

    print()
    print(sep)
    print(header)
    print(sep)

    for result in results:
        row = "|"
        for _, key, width in columns:
            val = result.get(key, "—")
            if isinstance(val, int):
                # right-align numbers, left-align text
                cell = f" {val:>{width}} "
            else:
                cell = f" {str(val):<{width}} "
            row += cell + "|"
        print(row)

    print(sep)
    print()


# ── Runners ───────────────────────────────────────────────────────────────────

def _run(source: str) -> list[dict[str, Any]]:
    """Run the requested pipeline(s) and return a list of result dicts."""
    results: list[dict[str, Any]] = []

    if source in ("hdx", "all"):
        logger.info("--- Starting HDX pipeline ---")
        t0 = time.monotonic()
        result = run_hdx_pipeline()
        elapsed = time.monotonic() - t0
        result.setdefault("source", "hdx")
        result.setdefault("rows_fetched", 0)
        result.setdefault("rows_clean", 0)
        result.setdefault("rows_quarantined", 0)
        result.setdefault("rows_duplicate", 0)
        result.setdefault("status", "unknown")
        logger.info("--- HDX pipeline finished in %.1fs ---", elapsed)
        results.append(result)

    if source in ("mofa", "all"):
        logger.info("--- Starting MoFA pipeline ---")
        t0 = time.monotonic()
        result = run_mofa_pipeline()
        elapsed = time.monotonic() - t0
        # MoFA returns aggregate keys; normalise to the shared summary shape.
        normalised: dict[str, Any] = {
            "source":           result.get("source", "mofa_srid"),
            "rows_fetched":     result.get("total_rows_fetched", 0),
            "rows_clean":       result.get("total_rows_clean", 0),
            "rows_quarantined": result.get("total_rows_quarantined", 0),
            "rows_duplicate":   result.get("rows_duplicate", 0),
            "status":           (
                "failed"
                if result.get("files_failed", 0) > 0
                and result.get("files_processed", 0) == 0
                else "success"
            ),
            "files_found":      result.get("files_found", 0),
            "files_processed":  result.get("files_processed", 0),
            "files_failed":     result.get("files_failed", 0),
        }
        logger.info("--- MoFA pipeline finished in %.1fs ---", elapsed)
        results.append(normalised)

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually trigger the AgriMatch ingestion pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_pipeline.py --source hdx\n"
            "  python run_pipeline.py --source mofa\n"
            "  python run_pipeline.py --source all\n"
        ),
    )
    parser.add_argument(
        "--source",
        choices=["hdx", "mofa", "all"],
        required=True,
        help="Which pipeline to run: hdx, mofa, or all.",
    )
    args = parser.parse_args()

    try:
        results = _run(args.source)
    except Exception:
        logger.exception("Pipeline run failed with an unhandled exception")
        sys.exit(1)

    _print_summary(results)

    # Exit non-zero if any pipeline reported a failed status so CI can catch it.
    if any(r.get("status") == "failed" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
