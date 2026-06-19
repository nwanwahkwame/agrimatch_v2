"""Admin domain services — business logic that doesn't belong in route handlers."""

from datetime import date, timedelta

from db.repositories.admin_repo import AdminRepo
from db.repositories.ussd_repo import UssdRepo


class AdminService:

    @staticmethod
    def get_model_accuracy(db, limit: int = 20) -> list[dict]:
        """Pivot raw (market, model_type) rows into one dict per market."""
        rows = AdminRepo.get_model_accuracy(db)
        markets: dict[str, dict] = {}
        for r in rows:
            if r.market not in markets:
                markets[r.market] = {"market": r.market}
            if r.model_type == "xgboost":
                markets[r.market]["xgb"]           = float(r.accuracy_pct or 0)
                markets[r.market]["xgb_mae"]       = float(r.mae or 0)
                markets[r.market]["training_rows"] = int(r.training_rows or 0)
            elif r.model_type == "lstm":
                markets[r.market]["lstm"] = float(r.accuracy_pct or 0)
        return list(markets.values())[:limit]

    @staticmethod
    def get_market_status(last_price_date) -> str:
        """Classify a market as live or stale based on its last price date."""
        cutoff = date.today() - timedelta(days=3)
        return "live" if (last_price_date and last_price_date >= cutoff) else "stale"


class UssdService:

    @staticmethod
    def get_stats(db) -> dict:
        """Compute USSD analytics time windows here so the router stays thin."""
        from datetime import datetime, timezone

        now           = datetime.now(timezone.utc)
        today_start   = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start    = today_start - timedelta(days=7)
        active_cutoff = now - timedelta(minutes=10)

        return UssdRepo.get_stats(db, today_start, week_start, active_cutoff)
