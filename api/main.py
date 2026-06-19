import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from api.payment_gateway import SimulatedGateway
from api.admin_router import router as admin_router
from ingestion.ussd_handler import USSDHandler
from api.routers import (
    advisory,
    alerts,
    demand,
    forecasting,
    listings,
    logistics,
    matchmaking,
    prices,
    reference,
    reservations,
    strategy,
    ussd_routes,
)
from api.schemas.common import HealthCheck
from config.settings import LOG_LEVEL
from db.connection import get_session
from ingestion.alert_engine import AlertEngine
from ingestion.m3_api import router as m3_router
from models.byproduct_marketplace import ByproductMarketplace
from models.cooperative_logistics import CooperativeLogistics
from models.crop_recommender import CropRecommender
from models.delay_classifier import HarvestDelayClassifier
from models.logistics_cost import LogisticsCostModel
from models.lstm_predictor import LSTMPredictor
from models.matchmaking_engine import MatchmakingEngine
from models.strategy_generator import StrategyGenerator
from models.xgboost_predictor import XGBoostPredictor


# ── Structured JSON logging ───────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "ts":  self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "mod": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)


def _configure_logging(level: int) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


_configure_logging(LOG_LEVEL)
logger = logging.getLogger(__name__)

_ALLOWED_ORIGINS = [
    "https://agrimatch-psi.vercel.app",
    "https://agrimatch.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm DB connection pool so first request is not cold
    with get_session() as _db:
        _db.execute(text("SELECT 1"))

    xgb = XGBoostPredictor()
    n_xgb = xgb.load_models()
    app.state.xgb_predictor = xgb

    lstm = LSTMPredictor()
    n_lstm = lstm.load_models()
    app.state.lstm_predictor = lstm

    clf = HarvestDelayClassifier()
    clf.load_model()
    app.state.delay_clf = clf

    recommender = CropRecommender()
    recommender.xgb_predictor = xgb
    app.state.recommender = recommender

    # Single shared LogisticsCostModel -- injected into every model that needs it
    logistics = LogisticsCostModel()
    app.state.logistics = logistics

    strategy_gen = StrategyGenerator()
    strategy_gen.xgb_predictor  = xgb
    strategy_gen.lstm_predictor = lstm
    strategy_gen._logistics     = logistics
    app.state.strategy = strategy_gen

    matcher = MatchmakingEngine()
    matcher._logistics = logistics
    app.state.matcher  = matcher

    byproduct = ByproductMarketplace()
    byproduct._logistics = logistics
    app.state.byproduct  = byproduct

    coop = CooperativeLogistics()
    coop.xgb_predictor = xgb
    coop._logistics    = logistics
    app.state.coop = coop

    alerts_engine = AlertEngine()
    app.state.alerts = alerts_engine

    app.state.payment_gateway = SimulatedGateway()
    app.state.ussd_handler    = USSDHandler()
    app.state.started_at      = datetime.now(timezone.utc).isoformat()

    logger.info(
        "AgriMatch API ready -- XGBoost: %d models, LSTM: %d models",
        n_xgb, n_lstm,
    )

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        clf.update_all_active_declarations,
        CronTrigger(hour=7, minute=30),
        id="delay_update", misfire_grace_time=3_600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        coop.run,
        CronTrigger(hour=22, minute=0),
        id="coop_logistics", misfire_grace_time=3_600, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        alerts_engine.run_all_checks,
        CronTrigger(hour=8, minute=0),
        id="alerts_daily", misfire_grace_time=3_600, coalesce=True, max_instances=1,
    )

    def _reload_xgb():
        if xgb.maybe_reload_from_db():
            logger.info("XGBoost models hot-reloaded from model_store")

    scheduler.add_job(
        _reload_xgb,
        CronTrigger(hour="*/6", minute=0),
        id="xgb_reload", misfire_grace_time=3_600, coalesce=True, max_instances=1,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=True)


# ── App setup ─────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title="AgriMatch API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Api-Secret"],
)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    ms = round((time.monotonic() - t0) * 1000)
    logger.info(
        "%s %s %s %dms",
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response

# ── Error handling ───────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred."},
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health(request: Request) -> JSONResponse:
    db_ok = False
    try:
        with get_session() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    xgb  = getattr(request.app.state, "xgb_predictor", None)
    lstm = getattr(request.app.state, "lstm_predictor", None)
    xgb_count  = len(xgb.models)  if (xgb  and hasattr(xgb,  "models")) else 0
    lstm_count = len(lstm.models) if (lstm and hasattr(lstm, "models")) else 0

    is_ok = db_ok and xgb_count > 0
    body = HealthCheck(
        status="ok" if is_ok else "degraded",
        db=db_ok,
        xgb_models=xgb_count,
        lstm_models=lstm_count,
    )
    return JSONResponse(
        content=body.model_dump(),
        status_code=200 if is_ok else 503,
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(m3_router)
app.include_router(admin_router)
app.include_router(reference.router)
app.include_router(forecasting.router)
app.include_router(listings.router)
app.include_router(prices.router)
app.include_router(advisory.router)
app.include_router(matchmaking.router)
app.include_router(strategy.router)
app.include_router(logistics.router)
app.include_router(alerts.router)
app.include_router(reservations.router)
app.include_router(demand.router)
app.include_router(ussd_routes.router)
