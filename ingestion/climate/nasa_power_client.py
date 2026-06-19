"""
NASA POWER daily climate data ingestion client.

Fetches daily temperature, solar radiation, humidity, and wind speed
from the NASA POWER point API for all 260 Ghana districts using their
centroid coordinates, computes reference ET0 via FAO Penman-Monteith,
and upserts into nasa_power_daily.

Usage:
    from ingestion.climate.nasa_power_client import NASAPowerClient
    client = NASAPowerClient()
    client.run_backfill(date(2006, 1, 1), date(2023, 7, 15))
"""

import logging
import math
import time
from datetime import date, timedelta

import pandas as pd
import requests

from db.connection import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

_NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
_PARAMS   = "T2M,T2M_MAX,T2M_MIN,ALLSKY_SFC_SW_DWN,RH2M,WS2M"
_MISSING  = -999.0
_MAX_DAYS = 366   # NASA POWER hard limit per single request

_RENAME = {
    "T2M":              "temp_mean",
    "T2M_MAX":          "temp_max",
    "T2M_MIN":          "temp_min",
    "ALLSKY_SFC_SW_DWN":"solar_mj",
    "RH2M":             "humidity_pct",
    "WS2M":             "wind_ms",
}


def _date_chunks(start: date, end: date, max_days: int = _MAX_DAYS):
    """Yield (chunk_start, chunk_end) pairs no longer than max_days."""
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_days - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


class NASAPowerClient:

    # ── 1. Fetch one district ─────────────────────────────────────────────────

    def fetch_district(
        self,
        district_id: int,
        lat: float,
        lon: float,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        params = {
            "parameters": _PARAMS,
            "community":  "AG",
            "longitude":  lon,
            "latitude":   lat,
            "start":      start_date.strftime("%Y%m%d"),
            "end":        end_date.strftime("%Y%m%d"),
            "format":     "JSON",
            "user":       "agrimatch",
        }

        resp = requests.get(_NASA_URL, params=params, timeout=(10, 120))
        if not resp.ok:
            raise RuntimeError(
                f"NASA POWER request failed: HTTP {resp.status_code} "
                f"for district {district_id} ({lat:.4f}, {lon:.4f})"
            )

        payload = resp.json()
        param_data = payload["properties"]["parameter"]

        # Build DataFrame: index = date strings, columns = parameter names
        df = pd.DataFrame(param_data)
        df.replace(_MISSING, float("nan"), inplace=True)

        # Convert string dates (YYYYMMDD) to Python date objects
        df.index = pd.to_datetime(df.index, format="%Y%m%d").date
        df.index.name = "obs_date"
        df = df.reset_index()

        df["district_id"] = district_id
        return df

    # ── 2. FAO Penman-Monteith ET0 ────────────────────────────────────────────

    def calculate_et0(self, row) -> float:
        T    = row["T2M"]
        Tmax = row["T2M_MAX"]
        Tmin = row["T2M_MIN"]
        Rs   = row["ALLSKY_SFC_SW_DWN"]
        RH   = row["RH2M"]
        u2   = row["WS2M"]

        if any(v != v for v in [T, Tmax, Tmin, Rs, RH, u2]):  # NaN check
            return float("nan")

        # a. Saturation vapour pressure (kPa)
        es = 0.6108 * (
            math.exp(17.27 * Tmax / (Tmax + 237.3))
            + math.exp(17.27 * Tmin / (Tmin + 237.3))
        ) / 2

        # b. Actual vapour pressure (kPa)
        ea = es * RH / 100

        # c. Slope of vapour pressure curve (kPa/C)
        delta = (
            4098 * (0.6108 * math.exp(17.27 * T / (T + 237.3)))
            / (T + 237.3) ** 2
        )

        # d. Psychrometric constant (kPa/C)
        gamma = 0.067

        # e. Net radiation approximation (MJ/m2/day)
        Rn = 0.77 * Rs - 2.1

        # f. FAO PM equation (mm/day)
        numerator   = 0.408 * delta * Rn + gamma * (900 / (T + 273)) * u2 * (es - ea)
        denominator = delta + gamma * (1 + 0.34 * u2)

        et0 = numerator / denominator
        return round(max(et0, 0.0), 3)

    # ── 3. Persist ────────────────────────────────────────────────────────────

    def save_to_database(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        # Compute ET0 before renaming columns
        df = df.copy()
        df["et0_mm"] = df.apply(self.calculate_et0, axis=1)

        df = df.rename(columns=_RENAME)

        db_cols = [
            "obs_date", "district_id",
            "temp_mean", "temp_max", "temp_min",
            "solar_mj", "humidity_pct", "wind_ms", "et0_mm",
        ]
        df = df[db_cols]

        # Replace NaN with None so psycopg2 writes NULL
        df = df.where(df.notna(), other=None)
        records = df.to_dict(orient="records")

        with get_session() as s:
            before = s.execute(text("""
                SELECT COUNT(*) FROM nasa_power_daily
                WHERE obs_date = :d AND district_id = :did
            """), {
                "d":   records[0]["obs_date"],
                "did": records[0]["district_id"],
            }).scalar()

            s.execute(text("""
                INSERT INTO nasa_power_daily
                    (obs_date, district_id, temp_mean, temp_max, temp_min,
                     solar_mj, humidity_pct, wind_ms, et0_mm)
                VALUES
                    (:obs_date, :district_id, :temp_mean, :temp_max, :temp_min,
                     :solar_mj, :humidity_pct, :wind_ms, :et0_mm)
                ON CONFLICT (obs_date, district_id) DO NOTHING
            """), records)

            after = s.execute(text("""
                SELECT COUNT(*) FROM nasa_power_daily
                WHERE obs_date = :d AND district_id = :did
            """), {
                "d":   records[0]["obs_date"],
                "did": records[0]["district_id"],
            }).scalar()

        return after - before

    # ── 4. Run all districts for a date range ─────────────────────────────────

    def run_all_districts(self, start_date: date, end_date: date) -> dict:
        with get_session() as s:
            districts = s.execute(text("""
                SELECT id, centroid_lat, centroid_lon
                FROM ghana_districts
                ORDER BY id
            """)).all()

        chunks = list(_date_chunks(start_date, end_date))
        total  = len(districts)
        succeeded: list[int] = []
        failed: list[int]    = []
        total_inserted = 0
        api_call_count = 0

        for i, d in enumerate(districts, 1):
            district_ok = True

            for chunk_start, chunk_end in chunks:
                if api_call_count > 0:
                    time.sleep(0.5)
                api_call_count += 1

                try:
                    df = self.fetch_district(
                        d.id,
                        float(d.centroid_lat),
                        float(d.centroid_lon),
                        chunk_start,
                        chunk_end,
                    )
                    inserted = self.save_to_database(df)
                    total_inserted += inserted
                except Exception as exc:
                    logger.error(
                        "District %d chunk %s-%s failed: %s",
                        d.id, chunk_start, chunk_end, exc,
                    )
                    district_ok = False

            if district_ok:
                succeeded.append(d.id)
            else:
                failed.append(d.id)

            if i % 10 == 0 or i == total:
                logger.info("Processed %d/%d districts ...", i, total)

        return {
            "districts_total":     total,
            "districts_succeeded": len(succeeded),
            "districts_failed":    len(failed),
            "failed_district_ids": failed,
            "total_rows_inserted": total_inserted,
        }

    # ── 5. Backfill ───────────────────────────────────────────────────────────

    def run_backfill(self, start_date: date, end_date: date) -> dict:
        expected_days = (end_date - start_date).days + 1

        # Districts that already have complete data for the range
        with get_session() as s:
            rows = s.execute(text("""
                SELECT district_id, COUNT(DISTINCT obs_date) AS days_ingested
                FROM nasa_power_daily
                WHERE obs_date BETWEEN :start AND :end
                GROUP BY district_id
            """), {"start": start_date, "end": end_date}).all()

        complete_ids = {r.district_id for r in rows if r.days_ingested >= expected_days}

        with get_session() as s:
            all_districts = s.execute(text(
                "SELECT id FROM ghana_districts ORDER BY id"
            )).all()

        all_ids    = [r.id for r in all_districts]
        missing_ids = [did for did in all_ids if did not in complete_ids]

        logger.info(
            "Backfill %s to %s: %d districts total, %d complete, %d to fetch",
            start_date, end_date, len(all_ids), len(complete_ids), len(missing_ids),
        )

        if not missing_ids:
            logger.info("Nothing to fetch -- all districts already complete.")
            return {
                "districts_total":     len(all_ids),
                "districts_fetched":   0,
                "districts_failed":    0,
                "failed_district_ids": [],
                "total_rows_inserted": 0,
            }

        # Load coordinates for only the missing districts
        with get_session() as s:
            missing_districts = s.execute(text("""
                SELECT id, centroid_lat, centroid_lon
                FROM ghana_districts
                WHERE id = ANY(:ids)
                ORDER BY id
            """), {"ids": missing_ids}).all()

        chunks = list(_date_chunks(start_date, end_date))
        total_inserted = 0
        succeeded: list[int] = []
        failed: list[int]    = []
        api_call_count = 0
        total = len(missing_districts)

        for i, d in enumerate(missing_districts, 1):
            district_ok = True

            for chunk_start, chunk_end in chunks:
                if api_call_count > 0:
                    time.sleep(0.5)
                api_call_count += 1

                try:
                    df = self.fetch_district(
                        d.id,
                        float(d.centroid_lat),
                        float(d.centroid_lon),
                        chunk_start,
                        chunk_end,
                    )
                    inserted = self.save_to_database(df)
                    total_inserted += inserted
                except Exception as exc:
                    logger.error(
                        "District %d chunk %s-%s failed: %s",
                        d.id, chunk_start, chunk_end, exc,
                    )
                    district_ok = False

            if district_ok:
                succeeded.append(d.id)
            else:
                failed.append(d.id)

            if i % 10 == 0 or i == total:
                logger.info(
                    "Backfill progress: %d/%d districts processed ...", i, total
                )

        with get_session() as s:
            total_rows = s.execute(text(
                "SELECT COUNT(*) FROM nasa_power_daily"
            )).scalar()

        result = {
            "districts_total":     len(all_ids),
            "districts_fetched":   len(missing_districts),
            "districts_succeeded": len(succeeded),
            "districts_failed":    len(failed),
            "failed_district_ids": failed,
            "total_rows_inserted": total_inserted,
            "total_rows_in_db":    total_rows,
        }

        logger.info(
            "NASA POWER backfill done: %d fetched, %d inserted, %d failed",
            len(missing_districts), total_inserted, len(failed),
        )
        return result
