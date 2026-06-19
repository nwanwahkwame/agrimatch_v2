"""
APScheduler jobs that orchestrate the HDX and MoFA ingestion pipelines.

Pipeline order for both sources:
  fetch raw -> save to raw_prices -> validate -> transform -> load to clean_prices
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_SUBMITTED,
)
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, text

from db.connection import get_session
from db.models import IngestionLog, RawPrice
from ingestion.hdx_client import HDXClient
from ingestion.mofa_client import MoFAClient
from ingestion.retrain import run_full_retrain
from ingestion.transformers import (
    detect_mofa_columns,
    load_to_database,
    transform_batch_hdx,
    transform_batch_mofa,
)
from ingestion.validators import validate_batch

logger = logging.getLogger(__name__)


# ── Shared helper ─────────────────────────────────────────────────────────────

def _fetch_raw_payloads(raw_ids: list[int]) -> tuple[list[dict], list[int]]:
    """Return (payloads, ids) for the given raw_ids, in the same order.

    Rows missing from raw_prices are skipped with a warning so a partial DB
    write never aborts the rest of the pipeline.
    """
    if not raw_ids:
        return [], []

    with get_session() as session:
        db_rows = session.execute(
            select(RawPrice.id, RawPrice.raw_payload).where(
                RawPrice.id.in_(set(raw_ids))
            )
        ).all()

    payload_by_id: dict[int, dict] = {row.id: row.raw_payload for row in db_rows}

    payloads: list[dict] = []
    ordered_ids: list[int] = []
    for rid in raw_ids:
        if rid in payload_by_id:
            payloads.append(payload_by_id[rid])
            ordered_ids.append(rid)
        else:
            logger.warning("raw_id %s not found in raw_prices — skipping", rid)

    return payloads, ordered_ids


def _attach_raw_ids_to_quarantine(
    all_rows: list[dict],
    all_ids: list[int],
    passing_rows: list[dict],
    quarantine_rows: list[dict],
) -> None:
    """Stamp ``raw_id`` onto each quarantine row in-place.

    validate_batch and transform_batch return clean rows as the same dict
    objects from the input list (not copies), so id() comparison reliably
    identifies which input positions failed.  Quarantine rows are new dicts
    in the same relative order as the failing inputs.
    """
    passing_obj_ids = {id(row) for row in passing_rows}
    failed_raw_ids = [
        rid for row, rid in zip(all_rows, all_ids) if id(row) not in passing_obj_ids
    ]
    for qrow, rid in zip(quarantine_rows, failed_raw_ids):
        qrow["raw_id"] = rid


# ── HDX pipeline ──────────────────────────────────────────────────────────────

def run_hdx_pipeline() -> dict[str, Any]:
    """Full HDX ingestion pipeline: fetch -> validate -> transform -> load."""
    logger.info("=== HDX pipeline starting ===")

    # 1. Fetch and save raw rows
    hdx_result = HDXClient().run()
    rows_fetched: int = hdx_result["rows_fetched"]
    raw_ids: list[int] = hdx_result["raw_ids"]

    if not raw_ids:
        logger.warning("HDX pipeline: HDXClient returned no raw rows — aborting")
        return {
            "source": "hdx",
            "rows_fetched": 0,
            "rows_clean": 0,
            "rows_quarantined": 0,
            "status": "aborted",
        }

    # 2. Load raw payloads from DB
    raw_rows, ordered_ids = _fetch_raw_payloads(raw_ids)

    # 3. Validate
    valid_rows, rejected_rows = validate_batch(raw_rows, source="hdx")
    # valid_rows are the same dict objects from raw_rows; rejected_rows are new
    # dicts.  Attach raw_ids so load_to_database can quarantine them properly.
    _attach_raw_ids_to_quarantine(raw_rows, ordered_ids, valid_rows, rejected_rows)

    # Build valid_ids in the same order as valid_rows using identity lookup.
    orig_id_map = {id(row): rid for row, rid in zip(raw_rows, ordered_ids)}
    valid_ids = [orig_id_map[id(row)] for row in valid_rows]

    # 4. Transform
    clean_rows, transform_failed = transform_batch_hdx(valid_rows, valid_ids)
    # clean_rows carry raw_id already; transform_failed do not.
    clean_raw_id_set = {r["raw_id"] for r in clean_rows}
    failed_ids = [rid for rid in valid_ids if rid not in clean_raw_id_set]
    for failed_row, rid in zip(transform_failed, failed_ids):
        failed_row["raw_id"] = rid

    # 5. Load to database
    quarantine_rows = rejected_rows + transform_failed
    summary = load_to_database(
        clean_rows, quarantine_rows, source="hdx", rows_fetched=rows_fetched
    )

    # 6. Log summary
    rows_clean = summary["rows_clean"]
    rows_quarantined = summary["rows_quarantined"]
    logger.info(
        "HDX pipeline complete.  Fetched: %d, Clean: %d, Quarantined: %d",
        rows_fetched,
        rows_clean,
        rows_quarantined,
    )
    if rows_clean == 0 and rows_fetched > 0:
        logger.warning(
            "HDX pipeline produced zero clean rows from %d fetched — "
            "check the quarantine table for rejection reasons",
            rows_fetched,
        )

    return summary


# ── MoFA pipeline ─────────────────────────────────────────────────────────────

def run_mofa_pipeline() -> dict[str, Any]:
    """Full MoFA ingestion pipeline across all unprocessed inbox files.

    Each file is processed independently so one bad file does not block the
    others.  Per-file summaries are aggregated and returned.
    """
    logger.info("=== MoFA pipeline starting ===")

    mofa_result = MoFAClient().run()
    total_fetched: int = mofa_result["total_rows_fetched"]
    total_clean = 0
    total_quarantined = 0

    for file_result in mofa_result["file_results"]:
        if file_result["status"] != "success":
            continue

        file_raw_ids: list[int] = file_result.get("raw_ids") or []
        filename: str = file_result["file"]

        if not file_raw_ids:
            logger.debug("No raw rows for '%s' — skipping transform step", filename)
            continue

        logger.info(
            "Processing '%s': %d raw rows", filename, len(file_raw_ids)
        )

        # 2. Load raw payloads from DB
        raw_rows, ordered_ids = _fetch_raw_payloads(file_raw_ids)
        if not raw_rows:
            continue

        # 3. Detect MoFA column layout from the keys of the first payload row.
        #    All rows from one file share the same column structure because
        #    they came from the same DataFrame.
        col_map = detect_mofa_columns(pd.DataFrame([raw_rows[0]]))

        # 4. Validate
        valid_rows, rejected_rows = validate_batch(raw_rows, source="mofa_srid")
        _attach_raw_ids_to_quarantine(raw_rows, ordered_ids, valid_rows, rejected_rows)

        orig_id_map = {id(row): rid for row, rid in zip(raw_rows, ordered_ids)}
        valid_ids = [orig_id_map[id(row)] for row in valid_rows]

        # 5. Transform
        clean_rows, transform_failed = transform_batch_mofa(valid_rows, valid_ids, col_map)
        clean_raw_id_set = {r["raw_id"] for r in clean_rows}
        failed_ids = [rid for rid in valid_ids if rid not in clean_raw_id_set]
        for failed_row, rid in zip(transform_failed, failed_ids):
            failed_row["raw_id"] = rid

        # 6. Load to database (writes its own ingestion_log entry)
        quarantine_rows = rejected_rows + transform_failed
        file_summary = load_to_database(
            clean_rows,
            quarantine_rows,
            source="mofa_srid",
            rows_fetched=len(file_raw_ids),
        )

        total_clean += file_summary["rows_clean"]
        total_quarantined += file_summary["rows_quarantined"]
        logger.info(
            "File '%s' complete.  Clean: %d, Quarantined: %d",
            filename,
            file_summary["rows_clean"],
            file_summary["rows_quarantined"],
        )

    logger.info(
        "MoFA pipeline complete.  Fetched: %d, Clean: %d, Quarantined: %d",
        total_fetched,
        total_clean,
        total_quarantined,
    )
    if total_clean == 0 and total_fetched > 0:
        logger.warning(
            "MoFA pipeline produced zero clean rows from %d fetched — "
            "check the quarantine table for rejection reasons",
            total_fetched,
        )

    return {
        "source": "mofa_srid",
        "files_found": mofa_result["files_found"],
        "files_processed": mofa_result["files_processed"],
        "files_failed": mofa_result["files_failed"],
        "total_rows_fetched": total_fetched,
        "total_rows_clean": total_clean,
        "total_rows_quarantined": total_quarantined,
    }


# ── Climate helpers ───────────────────────────────────────────────────────────

def log_to_database(job_name: str, result: dict, error: Exception | None = None) -> None:
    """Insert a row into ingestion_log for any scheduled job."""
    with get_session() as session:
        session.add(IngestionLog(
            source=job_name,
            status="failed" if error else "success",
            error_detail=str(error) if error else None,
            rows_fetched=result.get("rows_fetched"),
            rows_clean=result.get("rows_clean") or result.get("rows_inserted"),
            rows_quarantined=result.get("rows_quarantined"),
        ))


_SQL_INDICATORS_SINGLE_DATE = text("""
INSERT INTO climate_indicators
    (indicator_date, district_id, spi_30day, et0_mm,
     csi_maize, csi_tomato, csi_onion, csi_cassava, csi_rice, csi_plantain,
     harvest_delay_days, flag_level, note)
WITH
chirps_win AS (
    SELECT district_id, obs_date, COALESCE(mean_rainfall_mm, 0.0) AS rain
    FROM chirps_daily
    WHERE obs_date >= :window_start AND obs_date <= :target_date
),
rolled AS (
    SELECT district_id, obs_date,
           SUM(rain) OVER (
               PARTITION BY district_id ORDER BY obs_date
               ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
           ) AS rain_30day
    FROM chirps_win
),
day_chirps AS (SELECT * FROM rolled WHERE obs_date = :target_date),
nasa_day   AS (SELECT district_id, et0_mm FROM nasa_power_daily
               WHERE obs_date = :target_date),
chirps_based AS (
    SELECT dc.district_id, dc.obs_date,
           CASE WHEN sb.baseline_std_mm IS NULL OR sb.baseline_std_mm = 0 THEN 0.0
                ELSE (dc.rain_30day - sb.baseline_mean_mm)
                     / sb.baseline_std_mm::double precision
           END AS spi_val,
           nd.et0_mm,
           CASE WHEN nd.et0_mm IS NULL THEN 'et0_unavailable'::text
                ELSE NULL END AS note
    FROM day_chirps dc
    LEFT JOIN spi_baselines sb
           ON sb.district_id   = dc.district_id
          AND sb.calendar_month = EXTRACT(MONTH FROM dc.obs_date)::int
    LEFT JOIN nasa_day nd ON nd.district_id = dc.district_id
),
nasa_only AS (
    SELECT nd.district_id, :target_date::date AS obs_date,
           0.0 AS spi_val, nd.et0_mm,
           'spi_unavailable'::text AS note
    FROM nasa_day nd
    LEFT JOIN day_chirps dc ON dc.district_id = nd.district_id
    WHERE dc.district_id IS NULL
),
combined AS (SELECT * FROM chirps_based UNION ALL SELECT * FROM nasa_only),
normed AS (
    SELECT district_id, obs_date, note,
           ROUND(spi_val::numeric, 3) AS spi_30day, et0_mm,
           LEAST(GREATEST(-spi_val / 2.0, 0.0), 1.0) AS spi_norm,
           CASE WHEN et0_mm IS NULL THEN 0.0
                ELSE LEAST(GREATEST((et0_mm - 2.0) / 8.0, 0.0), 1.0)
           END AS et0_norm
    FROM combined
),
csi AS (
    SELECT district_id, obs_date, spi_30day, et0_mm, note,
           ROUND((0.65 * spi_norm + 0.35 * et0_norm)::numeric, 3) AS csi_maize,
           ROUND((0.50 * spi_norm + 0.50 * et0_norm)::numeric, 3) AS csi_tomato,
           ROUND((0.55 * spi_norm + 0.45 * et0_norm)::numeric, 3) AS csi_onion,
           ROUND((0.60 * spi_norm + 0.40 * et0_norm)::numeric, 3) AS csi_cassava,
           ROUND((0.70 * spi_norm + 0.30 * et0_norm)::numeric, 3) AS csi_rice,
           ROUND((0.60 * spi_norm + 0.40 * et0_norm)::numeric, 3) AS csi_plantain
    FROM normed
),
worst AS (
    SELECT *, GREATEST(csi_maize, csi_tomato, csi_onion,
                       csi_cassava, csi_rice, csi_plantain) AS worst_csi
    FROM csi
)
SELECT obs_date AS indicator_date, district_id, spi_30day, et0_mm,
       csi_maize, csi_tomato, csi_onion, csi_cassava, csi_rice, csi_plantain,
       CASE WHEN worst_csi < 0.30 THEN 0 WHEN worst_csi < 0.55 THEN 3
            WHEN worst_csi < 0.75 THEN 9 ELSE 18 END AS harvest_delay_days,
       CASE WHEN worst_csi < 0.30 THEN 'normal' WHEN worst_csi < 0.55 THEN 'watch'
            WHEN worst_csi < 0.75 THEN 'warning' ELSE 'critical' END AS flag_level,
       note
FROM worst
ON CONFLICT (indicator_date, district_id) DO UPDATE
    SET spi_30day          = EXCLUDED.spi_30day,
        et0_mm             = EXCLUDED.et0_mm,
        csi_maize          = EXCLUDED.csi_maize,
        csi_tomato         = EXCLUDED.csi_tomato,
        csi_onion          = EXCLUDED.csi_onion,
        csi_cassava        = EXCLUDED.csi_cassava,
        csi_rice           = EXCLUDED.csi_rice,
        csi_plantain       = EXCLUDED.csi_plantain,
        harvest_delay_days = EXCLUDED.harvest_delay_days,
        flag_level         = EXCLUDED.flag_level,
        note               = EXCLUDED.note
""")


def recompute_indicators_for_date(target_date: date) -> dict:
    """Compute and upsert climate_indicators for a single date."""
    window_start = target_date - timedelta(days=30)
    with get_session() as session:
        result = session.execute(
            _SQL_INDICATORS_SINGLE_DATE,
            {"window_start": window_start, "target_date": target_date},
        )
        rows = max(result.rowcount, 0)
    return {"date": str(target_date), "rows_upserted": rows}


# ── M2 climate jobs ───────────────────────────────────────────────────────────

def run_chirps_daily() -> None:
    """Fetch yesterday-minus-one CHIRPS rainfall and insert into chirps_daily."""
    logger.info("=== CHIRPS daily update starting ===")
    try:
        from ingestion.climate.chirps_client import CHIRPSClient
        client = CHIRPSClient()
        target = date.today() - timedelta(days=2)
        result = client.run(target_date=target)
        log_to_database("chirps_daily_update", result)
        logger.info("CHIRPS daily update complete: %s", result)
    except Exception as exc:
        logger.exception("CHIRPS daily update failed")
        log_to_database("chirps_daily_update", {}, error=exc)


def run_nasa_power_daily() -> None:
    """Backfill last 7 days of NASA POWER weather into nasa_power_daily."""
    logger.info("=== NASA POWER daily update starting ===")
    try:
        from ingestion.climate.nasa_power_client import NASAPowerClient
        client = NASAPowerClient()
        end = date.today() - timedelta(days=2)
        start = end - timedelta(days=6)
        result = client.run_backfill(start_date=start, end_date=end)
        log_to_database("nasa_power_daily_update", result)
        logger.info("NASA POWER daily update complete: %s", result)
    except Exception as exc:
        logger.exception("NASA POWER daily update failed")
        log_to_database("nasa_power_daily_update", {}, error=exc)


def run_climate_indicators_daily() -> None:
    """Recompute climate_indicators for the date 2 days ago."""
    logger.info("=== Climate indicators daily update starting ===")
    try:
        target = date.today() - timedelta(days=2)
        result = recompute_indicators_for_date(target)
        log_to_database("climate_indicators_update", result)
        logger.info("Climate indicators update complete: %s", result)
    except Exception as exc:
        logger.exception("Climate indicators daily update failed")
        log_to_database("climate_indicators_update", {}, error=exc)


def run_fuel_price_scrape() -> None:
    """Scrape current NPA fuel prices and save to fuel_prices table."""
    logger.info("=== Fuel price weekly scrape starting ===")
    try:
        from ingestion.fuel_scraper import FuelScraper
        result = FuelScraper().run()
        logger.info("Fuel price scrape complete: %s", result)
    except Exception as exc:
        logger.exception("Fuel price scrape failed")
        log_to_database("fuel_price_scrape", {}, error=exc)


def run_spi_baseline_refresh() -> None:
    """Refresh SPI baselines from the full CHIRPS archive."""
    logger.info("=== SPI baseline weekly refresh starting ===")
    try:
        from setup.compute_spi_baselines import compute_baselines
        result = compute_baselines()
        log_to_database("spi_baseline_refresh", result)
        logger.info("SPI baseline refresh complete: %s", result)
    except Exception as exc:
        logger.exception("SPI baseline refresh failed")
        log_to_database("spi_baseline_refresh", {}, error=exc)


def run_csi_update() -> None:
    """Refresh CSI flags and adjusted harvest dates for all active declarations."""
    logger.info("=== CSI daily declaration update starting ===")
    try:
        from ingestion.csi_engine import CSIEngine
        summary = CSIEngine().run_all_active()
        log_to_database("csi_update", {
            "rows_fetched": summary["total_processed"],
            "rows_clean": summary["flag_changed"],
        })
        logger.info("CSI update complete: %s", summary)
    except Exception as exc:
        logger.exception("CSI daily update failed")
        log_to_database("csi_update", {}, error=exc)


def run_alerts_daily() -> None:
    """Run all SMS alert checks: price, CSI, logistics, and byproduct."""
    logger.info("=== Daily alert checks starting ===")
    try:
        from ingestion.alert_engine import AlertEngine
        summary = AlertEngine().run_all_checks()
        log_to_database("alerts_daily", {
            "rows_fetched": summary["total_sent"] + summary["total_failed"],
            "rows_clean":   summary["total_sent"],
        })
        logger.info("Alert run complete: %s", summary)
    except Exception as exc:
        logger.exception("Daily alert run failed")
        log_to_database("alerts_daily", {}, error=exc)


def run_cooperative_logistics() -> None:
    """Group active declarations into shared truck runs and save transport jobs."""
    logger.info("=== Cooperative logistics daily run starting ===")
    try:
        from models.cooperative_logistics import CooperativeLogistics
        summary = CooperativeLogistics().run()
        log_to_database("cooperative_logistics", {
            "rows_fetched": summary["total_farmers_in_groups"],
            "rows_clean":   summary["jobs_created"],
        })
        logger.info("Cooperative logistics complete: %s", summary)
    except Exception as exc:
        logger.exception("Cooperative logistics run failed")
        log_to_database("cooperative_logistics", {}, error=exc)


def run_transport_matching() -> None:
    """Match pending transport jobs to the best available real providers.

    Runs 30 minutes after cooperative_logistics so new jobs are already saved.
    """
    logger.info("=== Transport provider matching starting ===")
    try:
        from models.transport_matcher import match_pending_jobs
        summary = match_pending_jobs()
        log_to_database("transport_matching", {
            "rows_fetched": summary["jobs_examined"],
            "rows_clean":   summary["jobs_matched"],
            "rows_quarantined": summary["jobs_unmatched"],
        })
        logger.info("Transport matching complete: %s", summary)
    except Exception as exc:
        logger.exception("Transport matching run failed")
        log_to_database("transport_matching", {}, error=exc)


def run_model_retrain() -> None:
    """Refresh feature_store then retrain all XGBoost models; persist to model_store.

    Runs weekly (Sunday 10:00 UTC) so the API picks up fresh forecasts within
    6 hours via its hot-reload job without needing a redeployment.
    """
    logger.info("=== Weekly model retrain starting ===")
    try:
        summary = run_full_retrain()
        log_to_database("model_retrain", {
            "rows_fetched": summary.get("feature_store_rows_upserted", 0),
            "rows_clean":   summary.get("trained", 0),
            "rows_quarantined": summary.get("failed", 0),
        })
        logger.info("Model retrain complete: %s", summary)
    except Exception as exc:
        logger.exception("Weekly model retrain failed")
        log_to_database("model_retrain", {}, error=exc)


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _make_listener(scheduler: BlockingScheduler):
    """Return an APScheduler event listener that logs job lifecycle events."""

    job_label = {}  # maps job_id -> display name, populated on submit

    def on_submitted(event):
        job = scheduler.get_job(event.job_id)
        name = job.name if job else event.job_id
        job_label[event.job_id] = name
        logger.info("Job submitted: %s [id=%s]", name, event.job_id)

    def on_executed(event):
        name = job_label.get(event.job_id, event.job_id)
        logger.info("Job finished: %s [id=%s]", name, event.job_id)

    def on_error(event):
        name = job_label.get(event.job_id, event.job_id)
        logger.error(
            "Job failed: %s [id=%s] — %s",
            name,
            event.job_id,
            event.exception,
            exc_info=event.traceback,
        )

    return on_submitted, on_executed, on_error


def start_scheduler() -> None:
    """Configure and start the blocking scheduler.

    - HDX: daily at 07:00 UTC
    - MoFA: every Monday at 06:00 UTC

    Blocks until interrupted (Ctrl-C or SIGTERM).
    """
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        run_hdx_pipeline,
        trigger=CronTrigger(hour=7, minute=0, timezone="UTC"),
        id="hdx_daily",
        name="HDX daily price ingestion",
        misfire_grace_time=3_600,   # retry up to 1 h late if server was down
        coalesce=True,              # collapse multiple missed fires into one
    )

    scheduler.add_job(
        run_mofa_pipeline,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=0, timezone="UTC"),
        id="mofa_weekly",
        name="MoFA weekly Excel ingestion",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    # M2 climate jobs
    scheduler.add_job(
        run_chirps_daily,
        trigger=CronTrigger(hour=5, minute=0, timezone="UTC"),
        id="chirps_daily",
        name="CHIRPS daily rainfall update",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_nasa_power_daily,
        trigger=CronTrigger(hour=5, minute=30, timezone="UTC"),
        id="nasa_power_daily",
        name="NASA POWER daily weather update",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_climate_indicators_daily,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="climate_indicators_daily",
        name="Climate indicators daily update",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_fuel_price_scrape,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=30, timezone="UTC"),
        id="fuel_price_weekly",
        name="NPA fuel price weekly scrape",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_spi_baseline_refresh,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0, timezone="UTC"),
        id="spi_baseline_weekly",
        name="SPI baseline weekly refresh",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_csi_update,
        trigger=CronTrigger(hour=7, minute=0, timezone="UTC"),
        id="csi_daily",
        name="CSI daily declaration update",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_cooperative_logistics,
        trigger=CronTrigger(hour=22, minute=0, timezone="UTC"),
        id="cooperative_logistics_daily",
        name="Cooperative logistics daily grouping",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_transport_matching,
        trigger=CronTrigger(hour=22, minute=30, timezone="UTC"),
        id="transport_matching_daily",
        name="Transport provider matching",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_alerts_daily,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="alerts_daily",
        name="Daily SMS alert checks",
        misfire_grace_time=3_600,
        coalesce=True,
    )

    scheduler.add_job(
        run_model_retrain,
        trigger=CronTrigger(day_of_week="sun", hour=10, minute=0, timezone="UTC"),
        id="model_retrain_weekly",
        name="Weekly XGBoost model retrain",
        misfire_grace_time=7_200,   # allow up to 2 h late (retrain is slow)
        coalesce=True,
    )

    on_submitted, on_executed, on_error = _make_listener(scheduler)
    scheduler.add_listener(on_submitted, EVENT_JOB_SUBMITTED)
    scheduler.add_listener(on_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(on_error, EVENT_JOB_ERROR)

    now_utc = datetime.now(timezone.utc)
    job_lines = []
    for job in scheduler.get_jobs():
        next_run = job.trigger.get_next_fire_time(None, now_utc)
        next_str = next_run.strftime("%Y-%m-%d %H:%M UTC") if next_run else "unknown"
        job_lines.append(f"  {job.name:<40} next: {next_str}")
    logger.info("Scheduler starting with %d jobs:\n%s", len(job_lines), "\n".join(job_lines))

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    start_scheduler()
