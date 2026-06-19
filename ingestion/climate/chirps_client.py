"""
CHIRPS v2.0 daily rainfall ingestion client.

Downloads daily GeoTIFF files from the CHIRPS FTP server, clips to Ghana,
aggregates mean rainfall to district level, and upserts into chirps_daily.

Usage:
    from ingestion.climate.chirps_client import CHIRPSClient
    client = CHIRPSClient()
    summary = client.run()                                    # yesterday
    client.run_backfill(date(2022, 1, 1), date(2022, 12, 31))
"""

import gzip
import logging
import shutil
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.transform as rtransform
import requests
from rasterio.windows import from_bounds
from shapely.geometry import Point

from db.connection import get_engine, get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

_CHIRPS_BASE = (
    "https://data.chc.ucsb.edu/products/CHIRPS-2.0"
    "/global_daily/tifs/p05"
)
_NODATA = -9999.0

# Ghana bounding box (WGS84 degrees)
_GHA_MIN_LON = -3.25
_GHA_MAX_LON =  1.20
_GHA_MIN_LAT =  4.50
_GHA_MAX_LAT = 11.20


class CHIRPSClient:

    def __init__(self, tmp_dir: str | None = None) -> None:
        self._tmp = Path(tmp_dir) if tmp_dir else Path(tempfile.gettempdir()) / "chirps"
        self._tmp.mkdir(parents=True, exist_ok=True)

    # ── 1. URL builder ────────────────────────────────────────────────────────

    def get_download_url(self, target_date: date) -> str:
        date_str = target_date.strftime("%Y.%m.%d")
        return f"{_CHIRPS_BASE}/{target_date.year}/chirps-v2.0.{date_str}.tif.gz"

    # ── 2. Download + decompress ──────────────────────────────────────────────

    def download_tif(self, target_date: date) -> Path:
        url = self.get_download_url(target_date)
        stamp = target_date.strftime("%Y%m%d")
        gz_path  = self._tmp / f"chirps_{stamp}.tif.gz"
        tif_path = self._tmp / f"chirps_{stamp}.tif"

        logger.info("Downloading %s", url)
        for attempt in range(2):
            resp = requests.get(url, stream=True, timeout=(10, 300))
            if resp.status_code in (429, 503) and attempt == 0:
                logger.warning(
                    "HTTP %s for %s -- waiting 60s before retry", resp.status_code, url
                )
                time.sleep(60)
                continue
            if not resp.ok:
                raise RuntimeError(
                    f"CHIRPS download failed: HTTP {resp.status_code} for {url}"
                )
            break

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        last_milestone = -1

        with gz_path.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                fh.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = int(downloaded / total * 100)
                    milestone = (pct // 25) * 25
                    if milestone > last_milestone:
                        last_milestone = milestone
                        logger.info(
                            "  Download %d%% (%d / %d bytes)",
                            milestone, downloaded, total,
                        )

        logger.info("Decompressing %s", gz_path.name)
        with gzip.open(gz_path, "rb") as gz_in, tif_path.open("wb") as tif_out:
            shutil.copyfileobj(gz_in, tif_out)

        gz_path.unlink()
        logger.info("GeoTIFF ready: %s", tif_path)
        return tif_path

    # ── 3. Extract Ghana rainfall pixels ──────────────────────────────────────

    def extract_ghana_rainfall(
        self, tif_path: Path, target_date: date
    ) -> gpd.GeoDataFrame:
        with rasterio.open(tif_path) as src:
            window = from_bounds(
                _GHA_MIN_LON, _GHA_MIN_LAT, _GHA_MAX_LON, _GHA_MAX_LAT,
                src.transform,
            )
            data = src.read(1, window=window)
            win_transform = src.window_transform(window)

        # Mask nodata and negative sentinel values
        valid_mask = (data != _NODATA) & (data >= 0)
        rows, cols = np.where(valid_mask)

        if rows.size == 0:
            logger.warning(
                "No valid CHIRPS pixels found for Ghana on %s", target_date
            )
            return gpd.GeoDataFrame(
                columns=["longitude", "latitude", "rainfall_mm", "geometry"],
                crs="EPSG:4326",
            )

        lons, lats = rtransform.xy(win_transform, rows, cols)
        rainfall = data[rows, cols].astype(float)

        gdf = gpd.GeoDataFrame(
            {
                "longitude": np.asarray(lons),
                "latitude":  np.asarray(lats),
                "rainfall_mm": rainfall,
                "geometry": [Point(lon, lat) for lon, lat in zip(lons, lats)],
            },
            crs="EPSG:4326",
        )
        logger.info(
            "Extracted %d valid cells for %s (%.2f - %.2f mm)",
            len(gdf), target_date, rainfall.min(), rainfall.max(),
        )
        return gdf

    # ── 4. Spatial join to districts ──────────────────────────────────────────

    def aggregate_to_districts(
        self, gdf_cells: gpd.GeoDataFrame, target_date: date
    ) -> pd.DataFrame:
        if gdf_cells.empty:
            return pd.DataFrame(
                columns=["obs_date", "district_id", "mean_rainfall_mm", "cell_count"]
            )

        engine = get_engine()
        districts = gpd.read_postgis(
            "SELECT id AS district_id, geometry FROM ghana_districts",
            con=engine,
            geom_col="geometry",
            crs="EPSG:4326",
        )

        joined = gpd.sjoin(gdf_cells, districts, how="inner", predicate="within")

        agg = (
            joined.groupby("district_id")["rainfall_mm"]
            .agg(mean_rainfall_mm="mean", cell_count="count")
            .reset_index()
        )
        agg["obs_date"] = target_date
        agg["mean_rainfall_mm"] = agg["mean_rainfall_mm"].round(3)

        logger.info(
            "Aggregated to %d districts for %s", len(agg), target_date
        )
        return agg[["obs_date", "district_id", "mean_rainfall_mm", "cell_count"]]

    # ── 5. Persist ────────────────────────────────────────────────────────────

    def save_to_database(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        records = [
            {
                "obs_date":         row.obs_date,
                "district_id":      int(row.district_id),
                "mean_rainfall_mm": float(row.mean_rainfall_mm),
                "cell_count":       int(row.cell_count),
            }
            for row in df.itertuples(index=False)
        ]

        # Single executemany call — one round-trip avoids Neon idle-timeout
        # that occurs when the spatial join computation precedes many small inserts.
        with get_session() as s:
            before = s.execute(text(
                "SELECT COUNT(*) FROM chirps_daily WHERE obs_date = :d",
            ), {"d": records[0]["obs_date"]}).scalar()

            s.execute(text("""
                INSERT INTO chirps_daily
                    (obs_date, district_id, mean_rainfall_mm, cell_count)
                VALUES
                    (:obs_date, :district_id, :mean_rainfall_mm, :cell_count)
                ON CONFLICT (obs_date, district_id) DO NOTHING
            """), records)

            after = s.execute(text(
                "SELECT COUNT(*) FROM chirps_daily WHERE obs_date = :d",
            ), {"d": records[0]["obs_date"]}).scalar()

        inserted = after - before
        logger.info("Inserted %d of %d rows into chirps_daily", inserted, len(records))
        return inserted

    # ── 6. Run one date ───────────────────────────────────────────────────────

    def run(self, target_date: date | None = None) -> dict:
        if target_date is None:
            target_date = date.today() - timedelta(days=2)

        logger.info("CHIRPS run starting for %s", target_date)

        tif_path = self.download_tif(target_date)
        try:
            gdf_cells = self.extract_ghana_rainfall(tif_path, target_date)
            df = self.aggregate_to_districts(gdf_cells, target_date)
            inserted = self.save_to_database(df)
        finally:
            tif_path.unlink(missing_ok=True)

        mm_min = float(gdf_cells["rainfall_mm"].min()) if not gdf_cells.empty else None
        mm_max = float(gdf_cells["rainfall_mm"].max()) if not gdf_cells.empty else None

        summary = {
            "date":               target_date,
            "districts_with_data": len(df),
            "total_cells":        int(gdf_cells["rainfall_mm"].count()) if not gdf_cells.empty else 0,
            "mm_min":             mm_min,
            "mm_max":             mm_max,
            "rows_inserted":      inserted,
        }
        logger.info(
            "CHIRPS done: %s | %d districts | %d cells | %.2f-%.2f mm | %d inserted",
            target_date,
            summary["districts_with_data"],
            summary["total_cells"],
            mm_min or 0.0,
            mm_max or 0.0,
            inserted,
        )
        return summary

    # ── 7. Backfill ───────────────────────────────────────────────────────────

    def run_backfill(self, start_date: date, end_date: date, delay_seconds: float = 0) -> dict:
        all_dates: list[date] = []
        d = start_date
        while d <= end_date:
            all_dates.append(d)
            d += timedelta(days=1)

        # Fetch already-ingested dates in one query
        with get_session() as s:
            rows = s.execute(text("""
                SELECT DISTINCT obs_date FROM chirps_daily
                WHERE obs_date BETWEEN :start AND :end
            """), {"start": start_date, "end": end_date}).all()
        already_done = {r.obs_date for r in rows}

        missing = [d for d in all_dates if d not in already_done]
        logger.info(
            "Backfill %s to %s: %d total, %d already ingested, %d to process",
            start_date, end_date, len(all_dates), len(already_done), len(missing),
        )

        succeeded: list[date] = []
        failed: list[date] = []

        for i, d in enumerate(missing, 1):
            logger.info("Processing %s (%d of %d)", d, i, len(missing))
            if delay_seconds > 0 and i > 1:
                time.sleep(delay_seconds)
            try:
                self.run(d)
                succeeded.append(d)
            except Exception as exc:
                logger.error("Failed %s: %s", d, exc)
                failed.append(d)

        return {
            "dates_attempted": len(missing),
            "dates_succeeded": len(succeeded),
            "dates_failed":    len(failed),
            "failed_dates":    failed,
        }
