import hmac

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import Response

from api.dependencies import get_ussd_handler
from api.schemas.admin import USSDStatsResponse
from api.security import require_internal
from api.services.admin_service import UssdService
from db.connection import get_session
from ingestion.ussd_handler import USSDHandler

router = APIRouter()


@router.post("/api/ussd")
def ussd_callback(
    sessionId:   str = Form(...),
    phoneNumber: str = Form(...),
    text_input:  str = Form("", alias="text"),
    token:       str = Query(default=""),
    handler: USSDHandler = Depends(get_ussd_handler),
) -> Response:
    """Africa's Talking USSD callback -- returns CON/END plain-text response.

    Set AT_CALLBACK_TOKEN and include ?token=<value> in the AT dashboard URL.
    If the env var is not set, all requests are rejected to prevent open access.
    """
    callback_token = handler.callback_token
    if not callback_token:
        raise HTTPException(status_code=503, detail="USSD token not configured")
    if not hmac.compare_digest(token, callback_token):
        raise HTTPException(status_code=403, detail="Forbidden")
    result = handler.process(sessionId, phoneNumber, text_input)
    return Response(content=result, media_type="text/plain")


@router.get(
    "/api/admin/ussd/stats",
    dependencies=[Depends(require_internal)],
    response_model=USSDStatsResponse,
)
def ussd_stats():
    """Return USSD session analytics for the admin dashboard."""
    with get_session() as db:
        return UssdService.get_stats(db)
