import io
import json
import logging
from typing import Any

import pandas as pd
import requests

from config.settings import HDX_DATASET_ID
from db.connection import get_session
from db.models import RawPrice

logger = logging.getLogger(__name__)

_HDX_API = "https://data.humdata.org/api/3/action/package_show"
_BATCH = 500   # rows flushed per round-trip to avoid one giant transaction


class HDXClient:

    def __init__(self) -> None:
        self.dataset_id = HDX_DATASET_ID

    # ── 1. Resolve CSV download URL ───────────────────────────────────────────

    def get_csv_url(self) -> str:
        """Call the HDX CKAN API and return the download URL of the CSV resource."""
        logger.info("Fetching HDX metadata for dataset '%s'", self.dataset_id)
        resp = requests.get(
            _HDX_API,
            params={"id": self.dataset_id},
            timeout=30,
        )
        resp.raise_for_status()

        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(
                f"HDX API returned success=false for '{self.dataset_id}': "
                f"{body.get('error')}"
            )

        resources = body["result"]["resources"]
        csv_res = next(
            (r for r in resources if r.get("format", "").upper() == "CSV"),
            None,
        )
        if csv_res is None:
            available = [r.get("format") for r in resources]
            raise RuntimeError(
                f"No CSV resource found in HDX dataset '{self.dataset_id}'. "
                f"Available formats: {available}"
            )

        url = csv_res["url"]
        logger.info("Found CSV resource '%s' → %s", csv_res.get("name", ""), url)
        return url

    # ── 2. Stream CSV into a DataFrame ────────────────────────────────────────

    def download_csv(self, url: str) -> pd.DataFrame:
        """Stream the CSV from *url* and return it as a DataFrame."""
        logger.info("Streaming CSV from %s", url)
        buffer = io.BytesIO()

        with requests.get(url, timeout=(10, 300), stream=True) as resp:
            resp.raise_for_status()
            total_kb = int(resp.headers.get("content-length", 0)) // 1024
            received = 0
            for chunk in resp.iter_content(chunk_size=65_536):
                buffer.write(chunk)
                received += len(chunk)

        logger.info(
            "Download complete: %.1f KB / %d KB expected",
            received / 1024,
            total_kb,
        )

        buffer.seek(0)
        df = pd.read_csv(buffer, low_memory=False)
        logger.info("Parsed %d rows × %d columns", len(df), len(df.columns))
        return df

    # ── 3. Persist raw rows ───────────────────────────────────────────────────

    def save_raw_rows(self, df: pd.DataFrame, source_url: str) -> list[int]:
        """Insert every DataFrame row as a RawPrice record.

        Rows are flushed in batches of _BATCH so IDs are assigned without
        holding the entire dataset in one uncommitted transaction.
        Commit happens once when the session context manager exits cleanly.
        Returns the list of newly inserted IDs in insertion order.
        """
        # to_json → from_json forces all numpy scalar types to plain Python
        # primitives and converts NaN → None (null in JSONB).
        records: list[dict] = json.loads(df.to_json(orient="records"))
        n = len(records)
        logger.info("Inserting %d raw rows (batch size %d)…", n, _BATCH)

        orm_objects: list[RawPrice] = []
        with get_session() as session:
            for i, record in enumerate(records, start=1):
                obj = RawPrice(
                    source="hdx",
                    raw_payload=record,
                    file_ref=source_url,
                )
                session.add(obj)
                orm_objects.append(obj)

                if i % _BATCH == 0:
                    session.flush()
                    logger.debug("Flushed batch %d / %d", i, n)

            session.flush()   # flush any remaining rows to populate .id
            raw_ids = [obj.id for obj in orm_objects]

        first, last = (raw_ids[0], raw_ids[-1]) if raw_ids else (None, None)
        logger.info("Committed %d rows (IDs %s – %s)", len(raw_ids), first, last)
        return raw_ids

    # ── 4. Orchestrate ────────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Full ingestion pipeline: fetch → download → persist.

        Returns a summary dict with ``rows_fetched`` and ``raw_ids``.
        """
        logger.info("=== HDX ingestion run started (dataset: %s) ===", self.dataset_id)

        csv_url = self.get_csv_url()
        df = self.download_csv(csv_url)
        raw_ids = self.save_raw_rows(df, csv_url)

        result: dict[str, Any] = {
            "rows_fetched": len(df),
            "raw_ids": raw_ids,
        }
        logger.info(
            "=== HDX ingestion complete: %d rows ingested ===",
            len(raw_ids),
        )
        return result
