"""Typed response schemas for all admin endpoints."""

from typing import Literal, Optional

from pydantic import BaseModel


class AdminFarmerItem(BaseModel):
    id:           int
    name:         str
    phone:        str
    district:     str
    region:       str
    declarations: int
    status:       Literal["active", "declined"]
    joined:       Optional[str]


class FarmerStatusResponse(BaseModel):
    id:        int
    is_active: bool
    action:    str


class AdminMarketItem(BaseModel):
    id:            int
    name:          str
    canonical:     str
    region:        str
    district:      str
    is_major_hub:  bool
    crops_tracked: int
    last_updated:  Optional[str]
    status:        Literal["live", "stale"]


class DistrictItem(BaseModel):
    id:       int
    district: str
    region:   str
    lat:      Optional[float]
    lon:      Optional[float]


class CropItem(BaseModel):
    id:                  int
    name:                str
    unit:                str
    is_byproduct_source: bool
    byproduct_types:     list


class StatsResponse(BaseModel):
    active_farmers:      int
    total_markets:       int
    active_declarations: int
    total_value_ghs:     float


class RegionItem(BaseModel):
    region:         str
    market_count:   int
    district_count: int


class ModelAccuracyItem(BaseModel):
    market:        str
    xgb:           Optional[float] = None
    xgb_mae:       Optional[float] = None
    lstm:          Optional[float] = None
    training_rows: Optional[int]   = None


class IngestionRunItem(BaseModel):
    source:           str
    run_at:           Optional[str]
    rows_clean:       Optional[int]
    rows_quarantined: Optional[int]
    status:           Optional[str]


class PipelineStatsResponse(BaseModel):
    row_counts:  dict
    recent_runs: list[IngestionRunItem]


class USSDStatsResponse(BaseModel):
    sessions_today:  int
    sessions_week:   int
    active_sessions: int
    total_sessions:  int
    completed:       int
    dropped:         int
