from fastapi import APIRouter, Depends

from api.dependencies import get_alerts
from db.connection import get_session
from db.repositories.alerts_repo import AlertsRepo
from ingestion.alert_engine import AlertEngine

router = APIRouter()


@router.post("/api/alerts/run")
def alerts_run(alerts: AlertEngine = Depends(get_alerts)):
    """Manually trigger all SMS alert checks and return a summary."""
    return alerts.run_all_checks()


@router.get("/api/alerts/log/{farmer_id}")
def alerts_log(farmer_id: int, limit: int = 50):
    """Return recent alerts sent to a farmer."""
    with get_session() as db:
        items = AlertsRepo.get_for_farmer(db, farmer_id, limit)
    return {"farmer_id": farmer_id, "total": len(items), "alerts": items}
