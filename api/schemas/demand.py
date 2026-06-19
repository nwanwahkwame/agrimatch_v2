from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from api.validators import validate_ghana_phone


class BuyerRequestIn(BaseModel):
    crop:        str
    quantity_kg: float = Field(..., gt=0)
    region:      str   = ""
    target_date: Optional[date] = None
    buyer_name:  str
    buyer_phone: str
    notes:       str   = ""

    @field_validator("buyer_phone")
    @classmethod
    def phone(cls, v: str) -> str:
        return validate_ghana_phone(v)


class CreateDemandResponse(BaseModel):
    id: int
    created_at: str


class DemandItem(BaseModel):
    id: int
    crop: str
    quantity_kg: float
    region: str
    target_date: Optional[date] = None
    buyer_name: str
    notes: str
    status: str
    created_at: str
