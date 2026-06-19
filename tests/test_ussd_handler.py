"""
Live integration tests for USSDHandler against the real database.
No server needed - imports USSDHandler directly.

Usage:
    python tests/test_ussd_handler.py
"""

import sys

from sqlalchemy import text

from db.connection import get_session
from ingestion.ussd_handler import USSDHandler

NEW_PHONE   = "0244999888"
RET_PHONE   = "0244123456"
RET_NAME    = "Akosua Darko"
RET_DISTRICT = 32           # Ejura-Sekyedumase, Ashanti

passed = 0
failed = 0
handler = USSDHandler()


def _ok(label: str, detail: str = "") -> None:
    global passed
    passed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  PASS  {label}{suffix}")


def _fail(label: str, reason: str) -> None:
    global failed
    failed += 1
    print(f"  FAIL  {label}  -- {reason}")


def _check(cond: bool, label: str, ok_detail: str = "", fail_reason: str = "") -> None:
    if cond:
        _ok(label, ok_detail)
    else:
        _fail(label, fail_reason or "assertion failed")


def _get_session_row(session_id: str) -> dict:
    with get_session() as db:
        row = db.execute(
            text("""
                SELECT menu_state, declaration, farmer_id
                FROM ussd_sessions WHERE session_id = :sid
            """),
            {"sid": session_id},
        ).fetchone()
    if not row:
        return {}
    return {"state": row[0], "declaration": row[1] or {}, "farmer_id": row[2]}


# ── Setup ─────────────────────────────────────────────────────────────────────

print("\n[Setup] Preparing database ...")
with get_session() as db:
    # Clear USSD sessions for both phones
    db.execute(
        text("""
            DELETE FROM ussd_sessions
            WHERE phone_number IN (:p1, :p2)
        """),
        {"p1": NEW_PHONE, "p2": RET_PHONE},
    )

    # Clear USSD declarations for returning farmer (idempotent re-runs)
    db.execute(
        text("""
            DELETE FROM farmer_declarations
            WHERE source = 'ussd'
              AND farmer_id IN (
                  SELECT id FROM farmers WHERE phone_number = :phone
              )
        """),
        {"phone": RET_PHONE},
    )

    # Ensure returning farmer exists
    existing = db.execute(
        text("SELECT id FROM farmers WHERE phone_number = :phone"),
        {"phone": RET_PHONE},
    ).fetchone()
    if not existing:
        db.execute(
            text("""
                INSERT INTO farmers (full_name, phone_number, district_id, is_active)
                VALUES (:name, :phone, :did, true)
            """),
            {"name": RET_NAME, "phone": RET_PHONE, "did": RET_DISTRICT},
        )
        print(f"  Created returning farmer {RET_PHONE}")
    else:
        print(f"  Returning farmer {RET_PHONE} already exists (id={existing[0]})")

print("  Setup complete.\n")


# ── Test 1 -- First dial from new farmer ──────────────────────────────────────

print("[Test 1] First dial from new farmer")
r = handler.process("sess001", NEW_PHONE, "")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("not registered" in r.lower(), "response contains 'not registered'", r[:60])
sess = _get_session_row("sess001")
_check(sess.get("state") == "register_name", "session state = register_name", sess.get("state"))


# ── Test 2 -- New farmer enters name ──────────────────────────────────────────

print("\n[Test 2] New farmer enters name")
r = handler.process("sess001", NEW_PHONE, "Ama Boateng")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("Ashanti" in r, "response contains region options (Ashanti)", r[:80])
sess = _get_session_row("sess001")
_check(sess.get("state") == "register_district", "session state = register_district", sess.get("state"))
_check(sess.get("declaration", {}).get("name") == "Ama Boateng", "declaration.name = Ama Boateng",
       str(sess.get("declaration")))


# ── Test 3 -- New farmer selects region (Ashanti = 1) ────────────────────────

print("\n[Test 3] New farmer selects region")
r = handler.process("sess001", NEW_PHONE, "Ama Boateng*1")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("Confirm" in r, "response contains 'Confirm'", r[:80])
sess = _get_session_row("sess001")
_check(sess.get("state") == "register_confirm", "session state = register_confirm", sess.get("state"))


# ── Test 4 -- New farmer confirms registration ────────────────────────────────

print("\n[Test 4] New farmer confirms registration")
r = handler.process("sess001", NEW_PHONE, "Ama Boateng*1*1")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("Registration complete" in r, "response contains 'Registration complete'", r[:80])

with get_session() as db:
    new_farmer = db.execute(
        text("SELECT id, full_name, district_id FROM farmers WHERE phone_number = :phone"),
        {"phone": NEW_PHONE},
    ).fetchone()
_check(new_farmer is not None, "new farmer row exists in farmers table",
       f"id={new_farmer[0] if new_farmer else None}")

sess = _get_session_row("sess001")
_check(sess.get("farmer_id") is not None, "session has farmer_id set",
       f"farmer_id={sess.get('farmer_id')}")


# ── Test 5 -- Returning farmer first dial ─────────────────────────────────────

print("\n[Test 5] Returning farmer first dial")
r = handler.process("sess002", RET_PHONE, "")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("AgriMatch" in r, "response contains 'AgriMatch'", r[:60])
_check("1." in r and "2." in r and "3." in r, "response contains menu options 1,2,3", r[:100])


# ── Test 6 -- Returning farmer selects List produce (1) ──────────────────────

print("\n[Test 6] Returning farmer selects List produce")
r = handler.process("sess002", RET_PHONE, "1")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("Maize" in r or "maize" in r, "response contains crop options", r[:80])
sess = _get_session_row("sess002")
_check(sess.get("state") == "crop_select", "session state = crop_select", sess.get("state"))


# ── Test 7 -- Farmer selects Maize (1) ───────────────────────────────────────

print("\n[Test 7] Farmer selects Maize")
r = handler.process("sess002", RET_PHONE, "1*1")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("bags" in r.lower(), "response contains 'bags'", r[:80])
sess = _get_session_row("sess002")
_check(sess.get("declaration", {}).get("crop") == "maize",
       "declaration.crop = maize", str(sess.get("declaration")))


# ── Test 8 -- Farmer enters quantity ─────────────────────────────────────────

print("\n[Test 8] Farmer enters quantity 50")
r = handler.process("sess002", RET_PHONE, "1*1*50")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("week" in r.lower(), "response contains harvest time options", r[:100])
sess = _get_session_row("sess002")
qty = sess.get("declaration", {}).get("quantity_bags")
_check(qty == 50 or qty == 50.0, "declaration.quantity_bags = 50",
       f"got {qty}")


# ── Test 9 -- Farmer selects harvest time (3 weeks = 3) ──────────────────────

print("\n[Test 9] Farmer selects harvest time (3 weeks)")
r = handler.process("sess002", RET_PHONE, "1*1*50*3")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("Confirm listing" in r, "response contains 'Confirm listing'", r[:80])
_check("maize" in r.lower(), "response contains 'maize'", r[:100])
_check("50" in r, "response contains '50'", r[:100])
_check(len(r) <= 182, "response length <= 182", f"{len(r)} chars")


# ── Test 10 -- Farmer confirms declaration ────────────────────────────────────

print("\n[Test 10] Farmer confirms declaration")
r = handler.process("sess002", RET_PHONE, "1*1*50*3*1")
print(f"  Response: {r!r}")
_check(r.startswith("END"), "response starts with END")
_check("AM-" in r, "response contains 'AM-' reference", r[:80])
_check(len(r) <= 160, "response length <= 160", f"{len(r)} chars")

with get_session() as db:
    ret_farmer = db.execute(
        text("SELECT id FROM farmers WHERE phone_number = :phone"),
        {"phone": RET_PHONE},
    ).fetchone()
    if ret_farmer:
        decl_row = db.execute(
            text("""
                SELECT id, source FROM farmer_declarations
                WHERE farmer_id = :fid AND source = 'ussd'
                ORDER BY id DESC LIMIT 1
            """),
            {"fid": ret_farmer[0]},
        ).fetchone()
    else:
        decl_row = None
_check(decl_row is not None, "declaration row exists with source='ussd'",
       f"id={decl_row[0] if decl_row else None}")


# ── Test 11 -- Invalid quantity (text instead of number) ──────────────────────

print("\n[Test 11] Invalid quantity (text input)")
# Navigate sess003 to quantity entry, then submit 'abc'
r = handler.process("sess003", RET_PHONE, "1*1*abc")
print(f"  Response: {r!r}")
_check(r.startswith("CON"), "response starts with CON")
_check("invalid" in r.lower() or "number" in r.lower(),
       "response contains error about invalid number", r[:80])


# ── Test 12 -- Session state after END ───────────────────────────────────────

print("\n[Test 12] Session behaviour after confirmed END")
# sess002 ended in Test 10 (state='done'); calling with '1' should restart flow
r = handler.process("sess002", RET_PHONE, "1")
print(f"  Response: {r!r}")
_check(r.startswith("CON") or r.startswith("END"),
       "response starts with CON or END", r[:60])


# ── Summary ───────────────────────────────────────────────────────────────────

total = passed + failed
print(f"\n{'='*50}")
print(f"OVERALL: {passed}/{total} PASSED")
print(f"{'='*50}\n")

sys.exit(0 if failed == 0 else 1)
