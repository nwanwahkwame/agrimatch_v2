from typing import Optional

from pydantic import BaseModel


class ListingItem(BaseModel):
    declaration_id:        int
    farmer_name:           str
    crop:                  str
    quantity_kg:           float
    harvest_date:          Optional[str]   = None
    price_forecast_ghs:    Optional[float] = None
    csi_flag:              str             = "normal"
    adjusted_harvest_date: Optional[str]   = None
    district:              str             = "Unknown"
    region:                str             = "Unknown"
    match_score:           Optional[float] = None   # None on browse endpoints; computed on matchmaking
    distance_km:           Optional[float] = None
    delivery_cost_ghs:     Optional[float] = None
    landed_cost_per_kg:    Optional[float] = None
    source:                Optional[str]   = None
    is_new:                Optional[bool]  = None


class ListingsResponse(BaseModel):
    total_found: int
    results:     list[ListingItem]
