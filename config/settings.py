import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_log = logging.getLogger(__name__)


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── HDX ───────────────────────────────────────────────────────────────────
    HDX_DATASET_ID: str = "wfp-food-prices-for-ghana"

    # ── MOFA inbox ────────────────────────────────────────────────────────────
    MOFA_INBOX_PATH: Path = Path("data/mofa_inbox")

    # ── Alerting ──────────────────────────────────────────────────────────────
    ALERT_EMAIL: str = ""

    # ── Africa's Talking SMS/USSD ─────────────────────────────────────────────
    AT_USERNAME:       str = "sandbox"
    AT_API_KEY:        str = ""
    AT_SENDER_ID:      str = "AgriMatch"
    # Include ?token=<value> in the USSD callback URL registered in AT dashboard.
    AT_CALLBACK_TOKEN: str = ""

    # ── FX rate ───────────────────────────────────────────────────────────────
    # USD to GHS conversion used when ingesting WFP prices denominated in USD.
    # Update this value whenever the Bank of Ghana publishes a new reference rate.
    USD_TO_GHS_RATE: float = 15.0

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Scheduler ─────────────────────────────────────────────────────────────
    INGEST_CRON: str = "0 6 * * *"

    @model_validator(mode="after")
    def _warn_missing_optional_vars(self) -> "_Settings":
        if not self.AT_API_KEY:
            _log.warning(
                "AT_API_KEY is not set -- SMS and USSD alerts will be disabled"
            )
        if not self.ALERT_EMAIL:
            _log.warning(
                "ALERT_EMAIL is not set -- email alerts will be silently skipped"
            )
        return self


_s = _Settings()

# Backward-compatible module-level exports (existing importers unchanged)
DATABASE_URL:      str  = _s.DATABASE_URL
HDX_DATASET_ID:    str  = _s.HDX_DATASET_ID
MOFA_INBOX_PATH:   Path = _s.MOFA_INBOX_PATH
ALERT_EMAIL:       str  = _s.ALERT_EMAIL
AT_USERNAME:       str  = _s.AT_USERNAME
AT_API_KEY:        str  = _s.AT_API_KEY
AT_SENDER_ID:      str  = _s.AT_SENDER_ID
AT_CALLBACK_TOKEN: str   = _s.AT_CALLBACK_TOKEN
USD_TO_GHS_RATE:   float = _s.USD_TO_GHS_RATE
LOG_LEVEL:         int   = getattr(logging, _s.LOG_LEVEL.upper(), logging.INFO)
INGEST_CRON:       str   = _s.INGEST_CRON
