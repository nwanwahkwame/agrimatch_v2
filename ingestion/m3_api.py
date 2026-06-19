"""M3 farmer registration and declaration API endpoints."""

import json
import re
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, model_validator
from sqlalchemy import text

from db.connection import get_session

router = APIRouter(prefix="/api", tags=["m3"])

_DEFAULT_BAG_KG = 100.0
_MAX_BULK = 50
_CROP_CSI_COL = {
    "maize": "csi_maize",
    "tomato": "csi_tomato",
    "onion": "csi_onion",
    "cassava": "csi_cassava",
    "rice": "csi_rice",
    "plantain": "csi_plantain",
}


# ── Custom exceptions ─────────────────────────────────────────────────────────

class DuplicateDeclarationError(Exception):
    def __init__(self, existing_id: int):
        self.existing_id = existing_id
        super().__init__(f"Duplicate declaration id={existing_id} within 7 days of harvest_date")


# ── Pydantic models ───────────────────────────────────────────────────────────

class FarmerRegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    district_id: int
    registered_by: Optional[int] = None


class FarmerResponse(BaseModel):
    farmer_id: int
    full_name: str
    phone_number: str
    district_name: str
    is_new_registration: bool
    message: str


class ByproductInput(BaseModel):
    type: str
    quantity_kg: float


class DeclarationRequest(BaseModel):
    farmer_id: int
    crop: str
    quantity_bags: float
    district_id: int
    harvest_date: date
    source: str
    byproducts: list[ByproductInput] = []


class ByproductOut(BaseModel):
    id: int
    byproduct_type: str
    estimated_quantity_kg: Optional[float] = None
    is_perishable: bool
    available_date: date
    status: str


class DeclarationResponse(BaseModel):
    declaration_id: int
    farmer_id: int
    crop: str
    quantity_kg: float
    harvest_date: date
    adjusted_harvest_date: date
    price_forecast_ghs: Optional[float] = None
    price_forecast_total_ghs: Optional[float] = None
    byproduct_ids: list[int]
    source: str
    confirmation_sms: str


class DeclarationDetail(BaseModel):
    id: int
    farmer_id: int
    farmer_name: str
    district_name: str
    district_id: int
    crop: str
    quantity_kg: float
    harvest_date: date
    adjusted_harvest_date: Optional[date] = None
    status: str
    price_forecast_ghs: Optional[float] = None
    csi_flag: str
    current_csi_flag: Optional[str] = None
    source: str
    byproducts: list[ByproductOut]


class DeclarationSummary(BaseModel):
    id: int
    crop: str
    quantity_kg: float
    harvest_date: date
    status: str
    price_forecast_ghs: Optional[float] = None
    csi_flag: str
    byproduct_count: int


class DeclarationUpdateRequest(BaseModel):
    crop: Optional[str] = None
    quantity_bags: Optional[float] = None
    harvest_date: Optional[date] = None


class BulkDeclarationItem(BaseModel):
    farmer_id: int
    crop: str
    quantity_bags: float
    district_id: int
    harvest_date: date
    source: str
    agent_id: int
    byproducts: list[ByproductInput] = []


class BulkDeclarationRequest(BaseModel):
    declarations: list[BulkDeclarationItem]

    @model_validator(mode="after")
    def check_max(self):
        if len(self.declarations) > _MAX_BULK:
            raise ValueError(f"Bulk limit is {_MAX_BULK} declarations per request")
        return self


class BulkDeclarationResponse(BaseModel):
    success_count: int
    failed_count: int
    declaration_ids: list[int]
    errors: list[dict]


# ── Phone normalization ───────────────────────────────────────────────────────

def _normalize_phone(raw: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)]", "", raw)
    if cleaned.startswith("+233"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("233") and len(cleaned) >= 12:
        cleaned = "0" + cleaned[3:]
    digits = re.sub(r"\D", "", cleaned)
    if not (10 <= len(digits) <= 13):
        raise ValueError(
            f"Phone normalises to {len(digits)} digits; expected 10-13"
        )
    return digits


# ── DB query helpers ──────────────────────────────────────────────────────────

def _district_name(session, district_id: int) -> Optional[str]:
    row = session.execute(
        text("SELECT district_name FROM ghana_districts WHERE id = :id"),
        {"id": district_id},
    ).fetchone()
    return row[0] if row else None


def _crop_ref(session, crop: str) -> Optional[dict]:
    row = session.execute(
        text("""
            SELECT is_byproduct_source, byproduct_types, unit_conversions
            FROM crop_reference WHERE internal_name = :crop
        """),
        {"crop": crop},
    ).fetchone()
    if not row:
        return None
    return {
        "is_byproduct_source": bool(row[0]),
        "byproduct_types": row[1] or [],
        "unit_conversions": row[2] or {},
    }


def _bags_to_kg(unit_conversions: dict, quantity_bags: float) -> float:
    bag_kg = (
        unit_conversions.get("bag_kg")
        or unit_conversions.get("bag")
        or _DEFAULT_BAG_KG
    )
    return round(float(quantity_bags) * float(bag_kg), 2)


def _price_forecast(session, crop: str, district_id: int) -> Optional[float]:
    row = session.execute(
        text("""
            SELECT price_ghs FROM clean_prices
            WHERE crop = :crop AND district_id = :did
            ORDER BY price_date DESC LIMIT 1
        """),
        {"crop": crop, "did": district_id},
    ).fetchone()
    if row:
        return float(row[0])

    row = session.execute(
        text("""
            SELECT cp.price_ghs FROM clean_prices cp
            WHERE cp.crop = :crop
              AND cp.region = (
                  SELECT region FROM clean_prices
                  WHERE district_id = :did AND region IS NOT NULL LIMIT 1
              )
            ORDER BY cp.price_date DESC LIMIT 1
        """),
        {"crop": crop, "did": district_id},
    ).fetchone()
    if row:
        return float(row[0])

    row = session.execute(
        text("""
            SELECT price_ghs FROM clean_prices
            WHERE crop = :crop
            ORDER BY price_date DESC LIMIT 1
        """),
        {"crop": crop},
    ).fetchone()
    return float(row[0]) if row else None


def _csi_flag(session, district_id: int, crop: str) -> Optional[str]:
    col = _CROP_CSI_COL.get(crop)
    if col:
        row = session.execute(
            text(
                f"SELECT {col} FROM climate_indicators"
                f" WHERE district_id = :did AND {col} IS NOT NULL"
                f" ORDER BY indicator_date DESC LIMIT 1"
            ),
            {"did": district_id},
        ).fetchone()
        if row and row[0] is not None:
            v = float(row[0])
            return "normal" if v < 0.30 else ("watch" if v < 0.60 else "alert")

    row = session.execute(
        text("""
            SELECT flag_level FROM climate_indicators
            WHERE district_id = :did
            ORDER BY indicator_date DESC LIMIT 1
        """),
        {"did": district_id},
    ).fetchone()
    return row[0] if row else None


def _build_sms(crop: str, quantity_kg: float, harvest_date: date,
               price_ghs: Optional[float], declaration_id: int) -> str:
    if price_ghs:
        price_str = f"GHS{price_ghs:.2f}/kg"
        total_str = f" Total:GHS{price_ghs * quantity_kg:.0f}."
    else:
        price_str = "N/A"
        total_str = ""
    sms = (
        f"AgriMatch: {crop.title()} confirmed."
        f" {quantity_kg:.0f}kg, harvest {harvest_date}."
        f" Forecast:{price_str}.{total_str} Ref#{declaration_id}"
    )
    return sms[:160]


def _insert_declaration_row(
    session, *,
    farmer_id: int, submitted_by_agent: Optional[int], source: str,
    crop: str, quantity_kg: float, district_id: int,
    harvest_date: date, price_ghs: Optional[float],
) -> int:
    row = session.execute(
        text("""
            INSERT INTO farmer_declarations
                (farmer_id, submitted_by_agent, source, crop, quantity_kg,
                 district_id, harvest_date, adjusted_harvest_date,
                 status, price_forecast_ghs, csi_flag)
            VALUES
                (:farmer_id, :agent, :source, :crop, :quantity_kg,
                 :district_id, :harvest_date, :harvest_date,
                 'active', :price_ghs, 'normal')
            RETURNING id
        """),
        {
            "farmer_id": farmer_id, "agent": submitted_by_agent,
            "source": source, "crop": crop, "quantity_kg": quantity_kg,
            "district_id": district_id, "harvest_date": harvest_date,
            "price_ghs": price_ghs,
        },
    ).fetchone()
    return row[0]


def _insert_byproducts(session, declaration_id: int, bp_list: list[dict]) -> list[int]:
    ids = []
    for bp in bp_list:
        row = session.execute(
            text("""
                INSERT INTO byproduct_declarations
                    (declaration_id, byproduct_type, estimated_quantity_kg,
                     is_perishable, available_date, status)
                VALUES (:decl_id, :btype, :qty, :perishable, :avail, 'active')
                RETURNING id
            """),
            {
                "decl_id": declaration_id,
                "btype": bp["type"],
                "qty": bp.get("quantity_kg"),
                "perishable": bp.get("is_perishable", False),
                "avail": bp["available_date"],
            },
        ).fetchone()
        ids.append(row[0])
    return ids


def _resolve_byproducts(
    user_list: list[ByproductInput],
    crop_ref: dict,
    quantity_kg: float,
    harvest_date: date,
) -> list[dict]:
    perishable_map = {
        bp["type"]: bp.get("is_perishable", False)
        for bp in (crop_ref.get("byproduct_types") or [])
    }

    if user_list:
        return [
            {
                "type": bp.type,
                "quantity_kg": bp.quantity_kg,
                "is_perishable": perishable_map.get(bp.type, False),
                "available_date": harvest_date,
            }
            for bp in user_list
        ]

    if crop_ref.get("is_byproduct_source"):
        return [
            {
                "type": bp_def["type"],
                "quantity_kg": round(quantity_kg * 0.3, 2),
                "is_perishable": bp_def.get("is_perishable", False),
                "available_date": harvest_date,
            }
            for bp_def in (crop_ref.get("byproduct_types") or [])
        ]

    return []


# ── Core declaration logic (shared by single and bulk) ────────────────────────

def _process_declaration(
    session, *,
    farmer_id: int, crop: str, quantity_bags: float, district_id: int,
    harvest_date: date, source: str, byproducts: list[ByproductInput],
    submitted_by_agent: Optional[int] = None,
) -> tuple[int, list[int], Optional[float], float]:
    """Validate and insert one declaration. Raises ValueError or DuplicateDeclarationError."""
    today = date.today()

    farmer_row = session.execute(
        text("SELECT id, is_active FROM farmers WHERE id = :id"),
        {"id": farmer_id},
    ).fetchone()
    if not farmer_row:
        raise ValueError(f"farmer_id {farmer_id} not found")
    if not farmer_row[1]:
        raise ValueError(f"farmer_id {farmer_id} is inactive")

    cr = _crop_ref(session, crop)
    if cr is None:
        supported = session.execute(
            text("SELECT internal_name FROM crop_reference ORDER BY internal_name")
        ).fetchall()
        supported_list = ", ".join(r[0] for r in supported)
        raise ValueError(
            f"'{crop}' is not a supported crop. "
            f"Supported crops are: {supported_list}. "
            f"Contact your extension officer if you grow a crop not listed."
        )

    if not _district_name(session, district_id):
        raise ValueError(f"district_id {district_id} not found")

    if harvest_date <= today:
        raise ValueError("harvest_date must be tomorrow or later")
    if harvest_date > today + timedelta(days=365):
        raise ValueError("harvest_date must be within 12 months from today")

    dup = session.execute(
        text("""
            SELECT id FROM farmer_declarations
            WHERE farmer_id = :fid AND crop = :crop AND district_id = :did
              AND harvest_date BETWEEN :lo AND :hi AND status = 'active'
            LIMIT 1
        """),
        {
            "fid": farmer_id, "crop": crop, "did": district_id,
            "lo": harvest_date - timedelta(days=7),
            "hi": harvest_date + timedelta(days=7),
        },
    ).fetchone()
    if dup:
        raise DuplicateDeclarationError(dup[0])

    quantity_kg = _bags_to_kg(cr["unit_conversions"], quantity_bags)
    price_ghs = _price_forecast(session, crop, district_id)

    decl_id = _insert_declaration_row(
        session,
        farmer_id=farmer_id,
        submitted_by_agent=submitted_by_agent,
        source=source,
        crop=crop,
        quantity_kg=quantity_kg,
        district_id=district_id,
        harvest_date=harvest_date,
        price_ghs=price_ghs,
    )

    bp_list = _resolve_byproducts(byproducts, cr, quantity_kg, harvest_date)
    bp_ids = _insert_byproducts(session, decl_id, bp_list)

    return decl_id, bp_ids, price_ghs, quantity_kg


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/farmers/register", status_code=status.HTTP_200_OK)
def register_farmer(body: FarmerRegisterRequest, response: Response) -> FarmerResponse:
    try:
        phone = _normalize_phone(body.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with get_session() as session:
        district = _district_name(session, body.district_id)
        if district is None:
            raise HTTPException(
                status_code=400,
                detail=f"district_id {body.district_id} not found",
            )

        existing = session.execute(
            text("SELECT id, full_name FROM farmers WHERE phone_number = :phone"),
            {"phone": phone},
        ).fetchone()

        if existing:
            return FarmerResponse(
                farmer_id=existing[0],
                full_name=existing[1],
                phone_number=phone,
                district_name=district,
                is_new_registration=False,
                message="already registered",
            )

        row = session.execute(
            text("""
                INSERT INTO farmers (full_name, phone_number, district_id, registered_by)
                VALUES (:name, :phone, :did, :reg_by)
                RETURNING id
            """),
            {
                "name": body.full_name,
                "phone": phone,
                "did": body.district_id,
                "reg_by": body.registered_by,
            },
        ).fetchone()

        response.status_code = status.HTTP_201_CREATED
        return FarmerResponse(
            farmer_id=row[0],
            full_name=body.full_name,
            phone_number=phone,
            district_name=district,
            is_new_registration=True,
            message="registered successfully",
        )


@router.post("/declarations", status_code=status.HTTP_201_CREATED)
def create_declaration(body: DeclarationRequest) -> DeclarationResponse:
    with get_session() as session:
        try:
            decl_id, bp_ids, price_ghs, quantity_kg = _process_declaration(
                session,
                farmer_id=body.farmer_id,
                crop=body.crop,
                quantity_bags=body.quantity_bags,
                district_id=body.district_id,
                harvest_date=body.harvest_date,
                source=body.source,
                byproducts=body.byproducts,
            )
        except DuplicateDeclarationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "duplicate_declaration",
                    "existing_declaration_id": exc.existing_id,
                    "message": "A similar declaration exists within 7 days of the requested harvest date",
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        total_ghs = round(price_ghs * quantity_kg, 2) if price_ghs else None
        sms = _build_sms(body.crop, quantity_kg, body.harvest_date, price_ghs, decl_id)

        return DeclarationResponse(
            declaration_id=decl_id,
            farmer_id=body.farmer_id,
            crop=body.crop,
            quantity_kg=quantity_kg,
            harvest_date=body.harvest_date,
            adjusted_harvest_date=body.harvest_date,
            price_forecast_ghs=price_ghs,
            price_forecast_total_ghs=total_ghs,
            byproduct_ids=bp_ids,
            source=body.source,
            confirmation_sms=sms,
        )


@router.get("/declarations/farmer/{farmer_id}")
def list_farmer_declarations(farmer_id: int) -> list[DeclarationSummary]:
    with get_session() as session:
        farmer = session.execute(
            text("SELECT id FROM farmers WHERE id = :id"),
            {"id": farmer_id},
        ).fetchone()
        if not farmer:
            raise HTTPException(status_code=404, detail=f"farmer_id {farmer_id} not found")

        rows = session.execute(
            text("""
                SELECT fd.id, fd.crop, fd.quantity_kg, fd.harvest_date,
                       fd.status, fd.price_forecast_ghs, fd.csi_flag,
                       COUNT(bd.id) AS byproduct_count
                FROM farmer_declarations fd
                LEFT JOIN byproduct_declarations bd ON bd.declaration_id = fd.id
                WHERE fd.farmer_id = :fid AND fd.status = 'active'
                GROUP BY fd.id, fd.crop, fd.quantity_kg, fd.harvest_date,
                         fd.status, fd.price_forecast_ghs, fd.csi_flag
                ORDER BY fd.harvest_date ASC
            """),
            {"fid": farmer_id},
        ).fetchall()

        return [
            DeclarationSummary(
                id=r[0],
                crop=r[1],
                quantity_kg=float(r[2]),
                harvest_date=r[3],
                status=r[4],
                price_forecast_ghs=float(r[5]) if r[5] is not None else None,
                csi_flag=r[6],
                byproduct_count=int(r[7]),
            )
            for r in rows
        ]


@router.get("/declarations/{declaration_id}")
def get_declaration(declaration_id: int) -> DeclarationDetail:
    with get_session() as session:
        row = session.execute(
            text("""
                SELECT fd.id, fd.farmer_id, f.full_name,
                       COALESCE(gd.district_name, fd.district_id::text) AS district_name,
                       fd.crop, fd.quantity_kg, fd.harvest_date,
                       fd.adjusted_harvest_date, fd.status,
                       fd.price_forecast_ghs, fd.csi_flag, fd.source,
                       fd.district_id
                FROM farmer_declarations fd
                JOIN farmers f ON f.id = fd.farmer_id
                LEFT JOIN ghana_districts gd ON gd.id = fd.district_id
                WHERE fd.id = :id
            """),
            {"id": declaration_id},
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Declaration {declaration_id} not found",
            )

        (decl_id, farmer_id, farmer_name, district_name, crop, quantity_kg,
         harvest_date, adjusted_harvest_date, dec_status, price_forecast_ghs,
         csi_flag_stored, source, district_id) = row

        current_flag = _csi_flag(session, district_id, crop)

        bp_rows = session.execute(
            text("""
                SELECT id, byproduct_type, estimated_quantity_kg,
                       is_perishable, available_date, status
                FROM byproduct_declarations
                WHERE declaration_id = :id
                ORDER BY id
            """),
            {"id": declaration_id},
        ).fetchall()

        byproducts = [
            ByproductOut(
                id=bp[0],
                byproduct_type=bp[1],
                estimated_quantity_kg=float(bp[2]) if bp[2] is not None else None,
                is_perishable=bool(bp[3]),
                available_date=bp[4],
                status=bp[5],
            )
            for bp in bp_rows
        ]

        return DeclarationDetail(
            id=decl_id,
            farmer_id=farmer_id,
            farmer_name=farmer_name,
            district_name=district_name,
            district_id=int(district_id),
            crop=crop,
            quantity_kg=float(quantity_kg),
            harvest_date=harvest_date,
            adjusted_harvest_date=adjusted_harvest_date,
            status=dec_status,
            price_forecast_ghs=float(price_forecast_ghs) if price_forecast_ghs is not None else None,
            csi_flag=csi_flag_stored,
            current_csi_flag=current_flag,
            source=source,
            byproducts=byproducts,
        )


@router.patch("/declarations/{declaration_id}", status_code=status.HTTP_200_OK)
def update_declaration(declaration_id: int, body: DeclarationUpdateRequest):
    """Update crop, quantity, or harvest date for an active declaration."""
    with get_session() as session:
        row = session.execute(
            text("SELECT id, crop, harvest_date, status FROM farmer_declarations WHERE id = :id"),
            {"id": declaration_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Declaration {declaration_id} not found")
        if row.status != "active":
            raise HTTPException(status_code=409, detail="Only active declarations can be edited")

        updates: dict = {}
        if body.crop is not None:
            updates["crop"] = body.crop
        if body.quantity_bags is not None:
            updates["quantity_kg"] = body.quantity_bags * _DEFAULT_BAG_KG
        if body.harvest_date is not None:
            updates["harvest_date"] = body.harvest_date
            updates["adjusted_harvest_date"] = body.harvest_date

        if "crop" in updates or "harvest_date" in updates:
            updates["price_forecast_ghs"] = None

        if not updates:
            return {"id": declaration_id, "updated": False}

        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        updates["id"] = declaration_id
        session.execute(
            text(f"UPDATE farmer_declarations SET {set_clauses} WHERE id = :id"),
            updates,
        )

    return {"id": declaration_id, "updated": True}


@router.delete("/declarations/{declaration_id}", status_code=status.HTTP_200_OK)
def cancel_declaration(declaration_id: int):
    """Soft-cancel an active declaration (sets status='cancelled')."""
    with get_session() as session:
        row = session.execute(
            text("SELECT id, status FROM farmer_declarations WHERE id = :id"),
            {"id": declaration_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Declaration {declaration_id} not found")
        if row.status != "active":
            raise HTTPException(status_code=409, detail="Declaration is not active")
        session.execute(
            text("UPDATE farmer_declarations SET status = 'cancelled' WHERE id = :id"),
            {"id": declaration_id},
        )
    return {"id": declaration_id, "cancelled": True}


# ── Transport constants ───────────────────────────────────────────────────────

_VALID_VEHICLE_TYPES = {"pickup", "mini_van", "medium_truck", "large_truck"}
_CAPACITY_RANGES: dict[str, tuple[float, float]] = {
    "pickup":       (500.0,   1_500.0),
    "mini_van":     (800.0,   2_000.0),
    "medium_truck": (2_000.0, 8_000.0),
    "large_truck":  (8_000.0, 30_000.0),
}


# ── Transport Pydantic models ─────────────────────────────────────────────────

class TransportRegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    business_name: Optional[str] = None
    district_id: int
    truck_capacity_kg: float
    truck_count: int = 1
    vehicle_type: str
    service_regions: list[str] = []
    base_rate_per_km: Optional[float] = None


class TransportRegisterResponse(BaseModel):
    provider_id: int
    full_name: str
    phone_number: str
    vehicle_type: str
    truck_capacity_kg: float
    district_name: str
    message: str


class TransportAvailableItem(BaseModel):
    provider_id: int
    full_name: str
    business_name: Optional[str] = None
    phone_number: str
    vehicle_type: str
    truck_capacity_kg: float
    truck_count: int
    base_rate_per_km: Optional[float] = None
    rating: float
    total_jobs: int
    base_district: str
    dist_from_base_km: float
    route_km: float
    estimated_cost_ghs: Optional[float] = None


# ── Transport endpoints ───────────────────────────────────────────────────────

@router.post("/transport/register", status_code=status.HTTP_201_CREATED)
def register_transport_provider(body: TransportRegisterRequest) -> TransportRegisterResponse:
    try:
        phone = _normalize_phone(body.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    vtype = body.vehicle_type.lower()
    if vtype not in _VALID_VEHICLE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"vehicle_type must be one of: {sorted(_VALID_VEHICLE_TYPES)}",
        )

    cap_min, cap_max = _CAPACITY_RANGES[vtype]
    if not (cap_min <= body.truck_capacity_kg <= cap_max):
        raise HTTPException(
            status_code=400,
            detail=(
                f"truck_capacity_kg for {vtype} must be between "
                f"{cap_min:.0f} and {cap_max:.0f} kg; got {body.truck_capacity_kg}"
            ),
        )

    with get_session() as session:
        district = _district_name(session, body.district_id)
        if district is None:
            raise HTTPException(
                status_code=400,
                detail=f"district_id {body.district_id} not found",
            )

        existing = session.execute(
            text("SELECT id FROM transport_providers WHERE phone_number = :phone"),
            {"phone": phone},
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "phone_already_registered",
                    "existing_provider_id": existing[0],
                    "message": f"Phone {phone} is already registered as a transport provider",
                },
            )

        row = session.execute(
            text("""
                INSERT INTO transport_providers
                    (full_name, phone_number, business_name, district_id,
                     truck_capacity_kg, truck_count, vehicle_type,
                     service_regions, base_rate_per_km)
                VALUES
                    (:name, :phone, :biz, :did,
                     :cap, :cnt, :vtype,
                     CAST(:regions AS jsonb), :rate)
                RETURNING id
            """),
            {
                "name": body.full_name,
                "phone": phone,
                "biz": body.business_name,
                "did": body.district_id,
                "cap": body.truck_capacity_kg,
                "cnt": body.truck_count,
                "vtype": vtype,
                "regions": json.dumps(body.service_regions),
                "rate": body.base_rate_per_km,
            },
        ).fetchone()

        return TransportRegisterResponse(
            provider_id=row[0],
            full_name=body.full_name,
            phone_number=phone,
            vehicle_type=vtype,
            truck_capacity_kg=body.truck_capacity_kg,
            district_name=district,
            message="registered successfully",
        )


@router.get("/transport/available")
def available_transport(
    district_id: int,
    cargo_kg: float,
    destination_district_id: int,
) -> list[TransportAvailableItem]:
    with get_session() as session:
        pickup_exists = session.execute(
            text("SELECT 1 FROM ghana_districts WHERE id = :id"),
            {"id": district_id},
        ).fetchone()
        if not pickup_exists:
            raise HTTPException(status_code=400, detail=f"district_id {district_id} not found")

        dest_exists = session.execute(
            text("SELECT 1 FROM ghana_districts WHERE id = :id"),
            {"id": destination_district_id},
        ).fetchone()
        if not dest_exists:
            raise HTTPException(
                status_code=400,
                detail=f"destination_district_id {destination_district_id} not found",
            )

        rows = session.execute(
            text("""
                SELECT
                    tp.id,
                    tp.full_name,
                    tp.business_name,
                    tp.phone_number,
                    tp.vehicle_type,
                    tp.truck_capacity_kg,
                    tp.truck_count,
                    tp.base_rate_per_km,
                    tp.rating,
                    tp.total_jobs,
                    gd_base.district_name AS base_district,
                    ROUND(sqrt(
                        power((gd_base.centroid_lat - gd_pickup.centroid_lat) * 111.0, 2) +
                        power((gd_base.centroid_lon - gd_pickup.centroid_lon) * 111.0
                              * cos(radians((gd_base.centroid_lat + gd_pickup.centroid_lat) / 2.0)), 2)
                    )::numeric, 1) AS dist_from_base_km,
                    ROUND(sqrt(
                        power((gd_pickup.centroid_lat - gd_dest.centroid_lat) * 111.0, 2) +
                        power((gd_pickup.centroid_lon - gd_dest.centroid_lon) * 111.0
                              * cos(radians((gd_pickup.centroid_lat + gd_dest.centroid_lat) / 2.0)), 2)
                    )::numeric, 1) AS route_km
                FROM transport_providers tp
                JOIN ghana_districts gd_base   ON gd_base.id   = tp.district_id
                JOIN ghana_districts gd_pickup ON gd_pickup.id = :pickup_did
                JOIN ghana_districts gd_dest   ON gd_dest.id   = :dest_did
                WHERE tp.is_available = true
                  AND tp.is_active    = true
                  AND tp.truck_capacity_kg >= :cargo_kg
                  AND (
                    jsonb_array_length(tp.service_regions) = 0
                    OR EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(tp.service_regions) AS sr
                        WHERE sr = gd_dest.region_name
                    )
                  )
                ORDER BY dist_from_base_km ASC
            """),
            {
                "pickup_did": district_id,
                "dest_did": destination_district_id,
                "cargo_kg": cargo_kg,
            },
        ).fetchall()

        results = []
        for r in rows:
            route_km = float(r[12])
            rate = float(r[7]) if r[7] is not None else None
            est_cost = round(rate * route_km, 2) if rate is not None else None
            results.append(TransportAvailableItem(
                provider_id=r[0],
                full_name=r[1],
                business_name=r[2],
                phone_number=r[3],
                vehicle_type=r[4],
                truck_capacity_kg=float(r[5]),
                truck_count=r[6],
                base_rate_per_km=rate,
                rating=float(r[8]),
                total_jobs=r[9],
                base_district=r[10],
                dist_from_base_km=float(r[11]),
                route_km=route_km,
                estimated_cost_ghs=est_cost,
            ))
        return results


@router.post("/declarations/bulk", status_code=status.HTTP_200_OK)
def bulk_declarations(body: BulkDeclarationRequest) -> BulkDeclarationResponse:
    declaration_ids: list[int] = []
    errors: list[dict] = []

    with get_session() as session:
        for i, item in enumerate(body.declarations):
            try:
                sp = session.begin_nested()
                decl_id, _, _, _ = _process_declaration(
                    session,
                    farmer_id=item.farmer_id,
                    crop=item.crop,
                    quantity_bags=item.quantity_bags,
                    district_id=item.district_id,
                    harvest_date=item.harvest_date,
                    source=item.source,
                    byproducts=item.byproducts,
                    submitted_by_agent=item.agent_id,
                )
                sp.commit()
                declaration_ids.append(decl_id)
            except DuplicateDeclarationError as exc:
                sp.rollback()
                errors.append({"index": i, "reason": str(exc)})
            except Exception as exc:
                sp.rollback()
                errors.append({"index": i, "reason": str(exc)})

    return BulkDeclarationResponse(
        success_count=len(declaration_ids),
        failed_count=len(errors),
        declaration_ids=declaration_ids,
        errors=errors,
    )
