from datetime import date, timedelta

from fastapi import APIRouter

from db.connection import get_session
from db.repositories.prices_repo import PricesRepo
from utils.cache import TtlCache

router = APIRouter()

_cache = TtlCache(ttl=3600)


def _fetch_bulletin():
    with get_session() as db:
        return PricesRepo.get_bulletin(db)


@router.get("/api/prices/history/{crop}")
def price_history(crop: str, market: str = "", months: int = 18):
    """Monthly average price for a crop, optionally filtered to one market."""
    start_date = (date.today() - timedelta(days=months * 30)).isoformat()
    with get_session() as db:
        return PricesRepo.get_price_history(db, crop, start_date, market)


@router.get("/api/prices/markets/{crop}")
def price_markets(crop: str):
    """Distinct markets that have price data for a crop."""
    with get_session() as db:
        return PricesRepo.get_markets_for_crop(db, crop)


@router.get("/api/market-bulletin")
def market_bulletin():
    """Latest price per crop x market, with 30-day change."""
    return _cache.get_or_set("bulletin", _fetch_bulletin)
