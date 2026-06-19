from typing import Optional

from pydantic import BaseModel


class ReservationResponse(BaseModel):
    status: str
    reservation_id: Optional[int] = None
    reference: str
    provider: str
    amount_ghs: Optional[float] = None
    message: str


class BuyerReservationItem(BaseModel):
    id: int
    declaration_id: int
    crop: str
    district: str
    region: str
    quantity_bags: int
    total_ghs: float
    status: str
    created_at: str
    reference: Optional[str] = None
    provider: Optional[str] = None
