"""
Re-process quarantined rows through the updated crop and unit mappings.

Reads directly from price_quarantine (which stores the original raw_payload),
re-runs the HDX transformer, inserts rows that now succeed into clean_prices,
and removes them from the quarantine table — all in one transaction.

Run after adding new CROP_MAP entries or _CROP_UNIT_FACTORS.
"""

import logging
from datetime import date as _date

from sqlalchemy import delete, insert, select

from db.connection import get_session
from db.models import CleanPrice, PriceQuarantine, RawPrice
from ingestion.transformers import transform_hdx_row

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Only attempt to rescue rows whose original failure reason is now fixed.
RESCUABLE_REASONS = {
    "unmapped_unit: Bunch",
    "unmapped_unit: 100 Tubers",
    "unmapped_crop: Fish (mackerel, fresh)",
    "unmapped_crop: Meat (chicken)",
    "unmapped_crop: Meat (chicken, local)",
    "unmapped_crop: Eggs",
}


def rescue() -> None:
    with get_session() as session:

        # 1. Load all rescuable quarantine rows, joined to get source.
        q_rows = session.execute(
            select(
                PriceQuarantine.id.label("q_id"),
                PriceQuarantine.raw_id,
                PriceQuarantine.rejection_reason,
                PriceQuarantine.raw_payload,
                RawPrice.source,
            )
            .join(RawPrice, RawPrice.id == PriceQuarantine.raw_id)
            .where(PriceQuarantine.rejection_reason.in_(RESCUABLE_REASONS))
        ).all()

        logger.info("Quarantine rows eligible for rescue: %d", len(q_rows))
        if not q_rows:
            logger.info("Nothing to rescue.")
            return

        # 2. Re-transform each row.
        clean_mappings: list[dict] = []
        rescued_q_ids: list[int] = []
        still_failed: list[tuple[int, str]] = []

        for row in q_rows:
            if row.source != "hdx":
                # MoFA rows need a col_map derived from the DataFrame; skip for now.
                still_failed.append((row.q_id, "mofa_rescue_not_implemented"))
                continue

            result, reason = transform_hdx_row(row.raw_payload, row.raw_id)
            if result:
                clean_mappings.append(result)
                rescued_q_ids.append(row.q_id)
            else:
                still_failed.append((row.q_id, reason))

        logger.info(
            "Re-transform result: %d succeeded, %d still failing",
            len(clean_mappings),
            len(still_failed),
        )

        # 3. Duplicate detection — same approach as load_to_database.
        existing_keys: set[tuple] = set()
        if clean_mappings:
            dates = [r["price_date"] for r in clean_mappings if r.get("price_date")]
            if dates:
                min_d, max_d = min(dates), max(dates)
                existing = session.execute(
                    select(
                        CleanPrice.market,
                        CleanPrice.crop,
                        CleanPrice.unit,
                        CleanPrice.price_date,
                        CleanPrice.source,
                    ).where(
                        CleanPrice.price_date >= min_d,
                        CleanPrice.price_date <= max_d,
                    )
                ).all()
                existing_keys = {tuple(r) for r in existing}

        new_rows = []
        duplicates = 0
        for r in clean_mappings:
            key = (r["market"], r["crop"], r["unit"], r["price_date"], r["source"])
            if key in existing_keys:
                duplicates += 1
            else:
                new_rows.append(r)

        if duplicates:
            logger.info("Skipped %d duplicate rows", duplicates)

        # 4. Bulk-insert rescued clean rows.
        if new_rows:
            session.execute(
                insert(CleanPrice),
                [
                    {
                        "raw_id":      r["raw_id"],
                        "market":      r["market"],
                        "region":      r["region"],
                        "district_id": r.get("district_id"),
                        "crop":        r["crop"],
                        "unit":        r["unit"],
                        "price_ghs":   r["price_ghs"],
                        "price_date":  r["price_date"],
                        "source":      r["source"],
                    }
                    for r in new_rows
                ],
            )
            logger.info("Inserted %d rescued rows into clean_prices", len(new_rows))

        # 5. Remove successfully rescued rows from quarantine.
        if rescued_q_ids:
            session.execute(
                delete(PriceQuarantine).where(
                    PriceQuarantine.id.in_(rescued_q_ids)
                )
            )
            logger.info("Removed %d rows from price_quarantine", len(rescued_q_ids))

        # Commit on context-manager exit.

    # 6. Print summary.
    print()
    print("=" * 60)
    print("  Rescue complete")
    print("=" * 60)
    print(f"  Eligible rows:     {len(q_rows):>6,}")
    print(f"  Rescued (clean):   {len(new_rows):>6,}")
    print(f"  Duplicates:        {duplicates:>6,}")
    print(f"  Still failing:     {len(still_failed):>6,}")
    if still_failed:
        from collections import Counter
        top = Counter(r for _, r in still_failed).most_common(5)
        print("  Top remaining reasons:")
        for reason, n in top:
            print(f"    {n:>5}  {reason}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    rescue()
