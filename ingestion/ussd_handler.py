"""USSD session handler for AgriMatch farmer registration and crop declaration."""

import json
import os
import re
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text

from db.connection import get_session


_REGIONS = [
    "Ashanti",
    "Greater Accra",
    "Northern",
    "Western",
    "Eastern",
    "Volta",
    "Central",
    "Upper East",
    "Upper West",
    "Brong-Ahafo",
]

_CROPS = ["maize", "tomato", "onion", "cassava", "rice", "plantain"]

_HARVEST_WEEKS = [1, 2, 3, 4]


def _norm_phone(raw: str) -> str:
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


def _get_alerts():
    """Lazy-init AlertEngine to avoid circular imports at module load."""
    from ingestion.alert_engine import AlertEngine
    return AlertEngine()


def send_confirmation_sms(
    phone: str,
    crop: str,
    qty_bags: float,
    harvest_date: date,
    decl_id: int,
    price_ghs: Optional[float],
    farmer_id: Optional[int] = None,
) -> bool:
    """Send declaration confirmation SMS and log to alerts_log."""
    price_part = f"GHS{price_ghs:.2f}/kg" if price_ghs else "N/A"
    msg = (
        f"AgriMatch: {crop.title()} listed. "
        f"{qty_bags:.0f} bags, harvest {harvest_date}. "
        f"Forecast:{price_part}. "
        f"Buyers will contact you. Ref:AM-{decl_id}"
    )[:160]
    return _get_alerts().send_sms(
        phone,
        msg,
        alert_type="ussd_confirmation",
        farmer_id=farmer_id,
    )


def send_registration_sms(
    phone: str,
    name: str,
    district_name: str,
    farmer_id: Optional[int] = None,
) -> bool:
    """Send registration welcome SMS and log to alerts_log."""
    first = name.split()[0]
    msg = (
        f"Welcome to AgriMatch, {first}! "
        f"You are now registered. "
        f"Dial *384# to list produce or check prices. "
        f"Your district: {district_name}."
    )[:160]
    return _get_alerts().send_sms(
        phone,
        msg,
        alert_type="ussd_registration",
        farmer_id=farmer_id,
    )


class USSDHandler:
    """Process one USSD callback and return a CON/END response string."""

    def __init__(self) -> None:
        self.callback_token: str = os.getenv("AT_CALLBACK_TOKEN", "")

    def process(self, session_id: str, phone: str, full_input: str) -> str:
        try:
            phone = _norm_phone(phone)
        except ValueError as exc:
            return f"END Error: {exc}"

        parts = full_input.split("*") if full_input else []
        sms_fn = None

        with get_session() as db:
            # Ensure session row exists
            exists = db.execute(
                text("SELECT 1 FROM ussd_sessions WHERE session_id = :sid"),
                {"sid": session_id},
            ).fetchone()
            if not exists:
                db.execute(
                    text("""
                        INSERT INTO ussd_sessions
                            (session_id, phone_number, menu_state, declaration)
                        VALUES (:sid, :phone, 'welcome', '{}'::jsonb)
                    """),
                    {"sid": session_id, "phone": phone},
                )

            # Resolve farmer
            farmer = db.execute(
                text("""
                    SELECT id, full_name, district_id
                    FROM farmers
                    WHERE phone_number = :phone AND is_active = true
                """),
                {"phone": phone},
            ).fetchone()

            if farmer is None:
                resp, state, decl, fid, sms_fn = self._reg_flow(db, parts, phone)
            else:
                resp, state, decl, fid, sms_fn = self._main_flow(db, parts, farmer, phone)

            db.execute(
                text("""
                    UPDATE ussd_sessions SET
                        menu_state    = :state,
                        declaration   = CAST(:decl AS jsonb),
                        farmer_id     = :fid,
                        last_activity = NOW()
                    WHERE session_id = :sid
                """),
                {
                    "state": state,
                    "decl": json.dumps(decl),
                    "fid": fid,
                    "sid": session_id,
                },
            )

        if sms_fn is not None:
            try:
                sms_fn()
            except Exception:
                pass  # never let SMS errors break the USSD response

        return resp

    # ── Registration flow ────────────────────────────────────────────────────

    def _reg_flow(self, db, parts: list[str], phone: str):
        if len(parts) == 0:
            return (
                "CON Welcome to AgriMatch.\nYou are not registered.\nEnter your full name:",
                "register_name",
                {},
                None,
                None,
            )

        if len(parts) == 1:
            name = parts[0].strip()
            if not name:
                return ("CON Please enter your full name:", "register_name", {}, None, None)
            region_list = "\n".join(f"{i+1}. {r}" for i, r in enumerate(_REGIONS))
            return (
                f"CON Select your region:\n{region_list}",
                "register_district",
                {"name": name},
                None,
                None,
            )

        if len(parts) == 2:
            name = parts[0].strip()
            try:
                idx = int(parts[1]) - 1
                if not (0 <= idx < len(_REGIONS)):
                    raise ValueError
                region = _REGIONS[idx]
            except ValueError:
                region_list = "\n".join(f"{i+1}. {r}" for i, r in enumerate(_REGIONS))
                return (
                    f"CON Invalid choice.\nSelect your region:\n{region_list}",
                    "register_district",
                    {"name": name},
                    None,
                    None,
                )
            return (
                f"CON Confirm registration:\nName: {name}\nRegion: {region}\n1. Confirm\n2. Cancel",
                "register_confirm",
                {"name": name, "region": region},
                None,
                None,
            )

        if len(parts) == 3:
            name = parts[0].strip()
            try:
                region = _REGIONS[int(parts[1]) - 1]
            except (ValueError, IndexError):
                return ("END Error processing registration.", "done", {}, None, None)

            if parts[2] == "1":
                dist = db.execute(
                    text("""
                        SELECT id, district_name FROM ghana_districts
                        WHERE region_name = :r ORDER BY id LIMIT 1
                    """),
                    {"r": region},
                ).fetchone()
                district_id   = dist[0] if dist else None
                district_name = dist[1] if dist else region

                row = db.execute(
                    text("""
                        INSERT INTO farmers (full_name, phone_number, district_id, is_active)
                        VALUES (:name, :phone, :did, true)
                        RETURNING id
                    """),
                    {"name": name, "phone": phone, "did": district_id},
                ).fetchone()
                fid = row[0]
                first = name.split()[0]

                def _sms_reg(p=phone, n=name, dn=district_name, fi=fid):
                    send_registration_sms(p, n, dn, fi)

                return (
                    f"CON Registration complete!\nWelcome {first}.\n1. List produce\n2. Check prices\n3. My listings",
                    "main_menu",
                    {},
                    fid,
                    _sms_reg,
                )
            return ("END Registration cancelled.", "done", {}, None, None)

        return ("END Session error. Please redial.", "done", {}, None, None)

    # ── Main flow for registered farmers ────────────────────────────────────

    def _main_flow(self, db, parts: list[str], farmer, phone: str):
        fid, fname, fdist = farmer[0], farmer[1], farmer[2]
        first = fname.split()[0]

        if not parts:
            return (
                f"CON Welcome to AgriMatch.\n{first}\n1. List produce\n2. Check prices\n3. My listings",
                "main_menu",
                {},
                fid,
                None,
            )

        choice = parts[0]

        if choice == "1":
            return self._produce_flow(db, parts, fid, fdist, phone)

        if choice == "2":
            return self._prices_flow(db, parts, fid)

        if choice == "3":
            return self._listings_flow(db, fid)

        return (
            f"CON Invalid choice.\n{first}\n1. List produce\n2. Check prices\n3. My listings",
            "main_menu",
            {},
            fid,
            None,
        )

    def _prices_flow(self, db, parts: list[str], fid: int):
        """Option 2: let farmer select a crop and see the latest market price."""
        _MENU = "1. List produce\n2. Check prices\n3. My listings"

        if len(parts) == 1:
            crop_list = "\n".join(f"{i+1}. {c.title()}" for i, c in enumerate(_CROPS))
            return (f"CON Select crop for price:\n{crop_list}", "prices_crop", {}, fid, None)

        try:
            idx = int(parts[1]) - 1
            if not (0 <= idx < len(_CROPS)):
                raise ValueError
            crop = _CROPS[idx]
        except ValueError:
            crop_list = "\n".join(f"{i+1}. {c.title()}" for i, c in enumerate(_CROPS))
            return (f"CON Invalid choice.\nSelect crop:\n{crop_list}", "prices_crop", {}, fid, None)

        row = db.execute(
            text("""
                SELECT price_ghs, market, price_date
                FROM clean_prices
                WHERE crop = :crop
                ORDER BY price_date DESC
                LIMIT 1
            """),
            {"crop": crop},
        ).fetchone()

        if not row:
            return (
                f"CON No price data for {crop.title()}.\n{_MENU}",
                "main_menu",
                {},
                fid,
                None,
            )

        price_str = f"GHS {float(row[0]):.2f}/kg"
        market    = str(row[1]).title()
        pdate     = str(row[2])
        return (
            f"END {crop.title()} price:\n{price_str}\nMarket: {market}\nDate: {pdate}",
            "done",
            {},
            fid,
            None,
        )

    def _listings_flow(self, db, fid: int):
        """Option 3: show the farmer's active declarations."""
        rows = db.execute(
            text("""
                SELECT crop, quantity_kg, harvest_date
                FROM farmer_declarations
                WHERE farmer_id = :fid AND status = 'active'
                ORDER BY harvest_date ASC
                LIMIT 3
            """),
            {"fid": fid},
        ).fetchall()

        if not rows:
            return (
                "END No active listings.\nDial again to list produce.",
                "done",
                {},
                fid,
                None,
            )

        lines = ["END Your active listings:"]
        for r in rows:
            bags   = int(float(r[1]) / 100)
            hdate  = str(r[2])
            lines.append(f"{r[0].title()} {bags}bags, {hdate}")

        return ("\n".join(lines), "done", {}, fid, None)

    def _produce_flow(self, db, parts: list[str], fid: int, fdist: Optional[int], phone: str):
        if len(parts) == 1:
            crop_list = "\n".join(f"{i+1}. {c.title()}" for i, c in enumerate(_CROPS))
            return (f"CON Select crop:\n{crop_list}", "crop_select", {}, fid, None)

        try:
            crop_idx = int(parts[1]) - 1
            if not (0 <= crop_idx < len(_CROPS)):
                raise ValueError
            crop = _CROPS[crop_idx]
        except ValueError:
            crop_list = "\n".join(f"{i+1}. {c.title()}" for i, c in enumerate(_CROPS))
            return (f"CON Invalid crop.\nSelect crop:\n{crop_list}", "crop_select", {}, fid, None)

        if len(parts) == 2:
            return (
                "CON Enter quantity in bags:\n(1 bag = 100kg)",
                "quantity_entry",
                {"crop": crop},
                fid,
                None,
            )

        try:
            qty = float(parts[2])
            if qty <= 0:
                raise ValueError
        except ValueError:
            return (
                "CON Invalid number. Enter quantity in bags:\n(1 bag = 100kg)",
                "quantity_entry",
                {"crop": crop},
                fid,
                None,
            )

        if len(parts) == 3:
            options = "\n".join(
                f"{i+1}. {w} week{'s' if w > 1 else ''}"
                for i, w in enumerate(_HARVEST_WEEKS)
            )
            return (
                f"CON Select harvest time:\n{options}",
                "harvest_select",
                {"crop": crop, "quantity_bags": qty},
                fid,
                None,
            )

        try:
            hw_idx = int(parts[3]) - 1
            if not (0 <= hw_idx < len(_HARVEST_WEEKS)):
                raise ValueError
            weeks = _HARVEST_WEEKS[hw_idx]
        except ValueError:
            options = "\n".join(
                f"{i+1}. {w} week{'s' if w > 1 else ''}"
                for i, w in enumerate(_HARVEST_WEEKS)
            )
            return (
                f"CON Invalid choice.\n{options}",
                "harvest_select",
                {"crop": crop, "quantity_bags": qty},
                fid,
                None,
            )

        harvest_date = date.today() + timedelta(weeks=weeks)

        if len(parts) == 4:
            return (
                f"CON Confirm listing:\n{crop} {qty:.0f} bags\nHarvest: {harvest_date}\n1. Confirm\n2. Cancel",
                "declare_confirm",
                {"crop": crop, "quantity_bags": qty, "harvest_weeks": weeks},
                fid,
                None,
            )

        if parts[4] == "1":
            qty_kg = qty * 100.0
            price_row = db.execute(
                text("""
                    SELECT price_ghs FROM clean_prices
                    WHERE crop = :crop AND district_id = :did
                    ORDER BY price_date DESC LIMIT 1
                """),
                {"crop": crop, "did": fdist},
            ).fetchone()
            price_ghs = float(price_row[0]) if price_row else None

            try:
                row = db.execute(
                    text("""
                        INSERT INTO farmer_declarations
                            (farmer_id, source, crop, quantity_kg, district_id,
                             harvest_date, adjusted_harvest_date,
                             status, price_forecast_ghs, csi_flag)
                        VALUES
                            (:fid, 'ussd', :crop, :qty_kg, :did,
                             :hdate, :hdate, 'active', :price, 'normal')
                        RETURNING id
                    """),
                    {
                        "fid": fid, "crop": crop, "qty_kg": qty_kg,
                        "did": fdist, "hdate": harvest_date, "price": price_ghs,
                    },
                ).fetchone()
                decl_id = row[0]

                def _sms_decl(p=phone, cr=crop, q=qty, hd=harvest_date, di=decl_id, pr=price_ghs, fi=fid):
                    send_confirmation_sms(p, cr, q, hd, di, pr, fi)

                return (
                    f"END Confirmed! Ref: AM-{decl_id}.\nCheck SMS for details.",
                    "done",
                    {},
                    fid,
                    _sms_decl,
                )
            except Exception:
                return ("END Error saving declaration. Please try again.", "done", {}, fid, None)

        return (
            "CON Listing cancelled.\n1. List produce\n2. Check prices\n3. My listings",
            "main_menu",
            {},
            fid,
            None,
        )
