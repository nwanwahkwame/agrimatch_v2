from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from api.dependencies import get_payment_gateway
from api.payment_gateway import PaymentGateway
from api.schemas.reservations import BuyerReservationItem, ReservationResponse
from api.security import require_internal
from api.services.reservation_service import ReservationService
from api.validators import validate_ghana_phone
from db.connection import get_session
from db.repositories.reservation_repo import ReservationRepo

router = APIRouter()


class ReservationRequest(BaseModel):
    declaration_id: int  = Field(..., gt=0)
    buyer_phone:    str
    buyer_name:     str  = Field(default="", max_length=120)
    quantity_bags:  int  = Field(default=1, ge=1, le=500)
    momo_phone:     str

    @field_validator("momo_phone", "buyer_phone")
    @classmethod
    def phone(cls, v: str) -> str:
        return validate_ghana_phone(v)


@router.post(
    "/api/reservations",
    dependencies=[Depends(require_internal)],
    response_model=ReservationResponse,
    status_code=201,
)
def create_reservation(req: ReservationRequest, gateway: PaymentGateway = Depends(get_payment_gateway)):
    """Create a reservation and MoMo payment record atomically."""
    return ReservationService.create(
        declaration_id=req.declaration_id,
        buyer_phone=req.buyer_phone,
        buyer_name=req.buyer_name,
        quantity_bags=req.quantity_bags,
        momo_phone=req.momo_phone,
        gateway=gateway,
    )


@router.get(
    "/api/reservations/buyer/{phone}",
    dependencies=[Depends(require_internal)],
    response_model=list[BuyerReservationItem],
)
def buyer_reservations(phone: str):
    """Return all reservations for a buyer's phone number."""
    with get_session() as db:
        rows = ReservationRepo.get_buyer_reservations(db, phone)
    return [
        {
            "id":             r.id,
            "declaration_id": r.declaration_id,
            "crop":           r.crop,
            "district":       r.district_name,
            "region":         r.region_name,
            "quantity_bags":  r.quantity_bags,
            "total_ghs":      float(r.total_ghs or 0),
            "status":         r.status,
            "created_at":     r.created_at.isoformat(),
            "reference":      r.reference,
            "provider":       r.provider,
        }
        for r in rows
    ]
