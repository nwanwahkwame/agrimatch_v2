"""
Live integration tests for M3 API endpoints.
Requires the server to be running at http://localhost:8000.

Usage:
    python tests/test_m3_endpoints.py
"""

import sys
from datetime import date, timedelta

import requests

BASE = "http://localhost:8000"
EJURA_DISTRICT_ID = 32
VALID_PHONE = "0244987001"  # unique enough to avoid clashes across runs

passed = 0
failed = 0
farmer_id = None
declaration_id = None


def _ok(label: str, detail: str = "") -> None:
    global passed
    passed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  PASS  {label}{suffix}")


def _fail(label: str, reason: str) -> None:
    global failed
    failed += 1
    print(f"  FAIL  {label}  -- {reason}")


def _check(condition: bool, label: str, pass_detail: str = "", fail_reason: str = "") -> None:
    if condition:
        _ok(label, pass_detail)
    else:
        _fail(label, fail_reason or "assertion failed")


# ── Test 1: Register new farmer ───────────────────────────────────────────────

print("\n[Test 1] Register new farmer")
r = requests.post(f"{BASE}/api/farmers/register", json={
    "full_name": "Kofi Mensah",
    "phone_number": VALID_PHONE,
    "district_id": EJURA_DISTRICT_ID,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 201:
    data = r.json()
    farmer_id = data.get("farmer_id")
    _check(farmer_id is not None, "farmer_id returned", f"id={farmer_id}")
    _check(data.get("is_new_registration") is True, "is_new_registration=true")
    _check(
        data.get("district_name") == "Ejura-Sekyedumase",
        "district_name correct",
        data.get("district_name"),
    )
elif r.status_code == 200:
    data = r.json()
    farmer_id = data.get("farmer_id")
    print(f"  NOTE: farmer already exists (id={farmer_id}), continuing with existing id")
    _ok("farmer_id returned (pre-existing)", f"id={farmer_id}")
    _check(data.get("is_new_registration") is False, "is_new_registration=false (pre-existing)")
    _fail("status 201 for new farmer", f"got {r.status_code} -- farmer already existed from a previous run")
else:
    _fail("POST /api/farmers/register", f"unexpected status {r.status_code}: {r.text}")


# ── Test 2: Register same farmer again (idempotency) ─────────────────────────

print("\n[Test 2] Register same farmer again (idempotency)")
r = requests.post(f"{BASE}/api/farmers/register", json={
    "full_name": "Kofi Mensah",
    "phone_number": VALID_PHONE,
    "district_id": EJURA_DISTRICT_ID,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code in (200, 201):
    data = r.json()
    _check(r.status_code == 200, "status 200 for duplicate", f"got {r.status_code}")
    _check(
        data.get("farmer_id") == farmer_id,
        "same farmer_id returned",
        f"id={data.get('farmer_id')}",
        f"expected {farmer_id} got {data.get('farmer_id')}",
    )
    _check(data.get("is_new_registration") is False, "is_new_registration=false")
else:
    _fail("POST /api/farmers/register (idempotency)", f"status {r.status_code}: {r.text}")


# ── Test 3: Submit a declaration ──────────────────────────────────────────────

print("\n[Test 3] Submit a declaration")
harvest_3wk = (date.today() + timedelta(weeks=3)).isoformat()
decl_payload = {
    "farmer_id": farmer_id,
    "crop": "maize",
    "quantity_bags": 80,
    "district_id": EJURA_DISTRICT_ID,
    "harvest_date": harvest_3wk,
    "source": "web",
}
r = requests.post(f"{BASE}/api/declarations", json=decl_payload)
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 201:
    data = r.json()
    declaration_id = data.get("declaration_id")
    _check(declaration_id is not None, "declaration_id returned", f"id={declaration_id}")
    _check(
        data.get("quantity_kg") == 8000.0,
        "quantity_kg = 8000 (80 bags x 100kg)",
        f"got {data.get('quantity_kg')}",
        f"expected 8000, got {data.get('quantity_kg')}",
    )
    _check(
        data.get("price_forecast_ghs") is not None,
        "price_forecast_ghs not null",
        f"GHS {data.get('price_forecast_ghs')}",
    )
    bp_ids = data.get("byproduct_ids", [])
    _check(len(bp_ids) > 0, "byproduct_ids not empty", f"{len(bp_ids)} byproducts")
    sms = data.get("confirmation_sms", "")
    _check(len(sms) <= 160, "confirmation_sms <= 160 chars", f"{len(sms)} chars: {sms!r}")
elif r.status_code == 409:
    data = r.json()
    declaration_id = data.get("detail", {}).get("existing_declaration_id")
    print(f"  NOTE: declaration already exists (id={declaration_id}), using existing for later tests")
    _fail("status 201 for new declaration", f"got 409 -- declaration already existed from a previous run")
else:
    _fail("POST /api/declarations", f"status {r.status_code}: {r.text}")


# ── Test 4: Duplicate declaration (409) ───────────────────────────────────────

print("\n[Test 4] Submit duplicate declaration (expect 409)")
r = requests.post(f"{BASE}/api/declarations", json=decl_payload)
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 409:
    data = r.json()
    detail = data.get("detail", {})
    _ok("status 409 returned")
    _check(
        detail.get("existing_declaration_id") is not None,
        "existing_declaration_id in response",
        f"id={detail.get('existing_declaration_id')}",
    )
else:
    _fail("duplicate declaration check", f"expected 409, got {r.status_code}: {r.text}")


# ── Test 5: Past harvest date validation ──────────────────────────────────────

print("\n[Test 5] Past harvest date (expect 400)")
yesterday = (date.today() - timedelta(days=1)).isoformat()
r = requests.post(f"{BASE}/api/declarations", json={
    "farmer_id": farmer_id,
    "crop": "maize",
    "quantity_bags": 10,
    "district_id": EJURA_DISTRICT_ID,
    "harvest_date": yesterday,
    "source": "web",
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 400, "status 400 for past harvest_date", f"got {r.status_code}")
if r.status_code == 400:
    detail = r.json().get("detail", "")
    _check(isinstance(detail, str) and len(detail) > 0, "error message present", detail)


# ── Test 6: Get declaration by id ─────────────────────────────────────────────

print("\n[Test 6] Get declaration by id")
if declaration_id is None:
    _fail("GET /api/declarations/{id}", "no declaration_id from Test 3")
else:
    r = requests.get(f"{BASE}/api/declarations/{declaration_id}")
    print(f"  Status: {r.status_code}  Body: {r.json()}")
    if r.status_code == 200:
        data = r.json()
        _check(data.get("crop") == "maize", "crop = maize", data.get("crop"))
        bps = data.get("byproducts", [])
        _check(len(bps) > 0, "byproducts list not empty", f"{len(bps)} byproducts")
        csi = data.get("csi_flag", "")
        valid_flags = {"normal", "watch", "alert"}
        _check(
            csi in valid_flags,
            "csi_flag is valid",
            csi,
            f"expected one of {valid_flags}, got '{csi}'",
        )
    else:
        _fail("GET /api/declarations/{id}", f"status {r.status_code}: {r.text}")


# ── Test 7: Get farmer declarations ──────────────────────────────────────────

print("\n[Test 7] Get farmer declarations")
r = requests.get(f"{BASE}/api/declarations/farmer/{farmer_id}")
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 200:
    data = r.json()
    _check(isinstance(data, list), "response is a list")
    _check(len(data) >= 1, "at least 1 declaration returned", f"{len(data)} declarations")
    if data:
        first = data[0]
        _check("harvest_date" in first, "harvest_date present in items")
        _check("byproduct_count" in first, "byproduct_count present in items")
else:
    _fail("GET /api/declarations/farmer/{id}", f"status {r.status_code}: {r.text}")


# ── Test 8: Bulk submission ───────────────────────────────────────────────────

print("\n[Test 8] Bulk submission (2 valid, 1 invalid)")
harvest_4wk = (date.today() + timedelta(weeks=4)).isoformat()
harvest_5wk = (date.today() + timedelta(weeks=5)).isoformat()
yesterday_str = (date.today() - timedelta(days=1)).isoformat()

bulk_payload = {
    "declarations": [
        {
            "farmer_id": farmer_id,
            "crop": "tomato",
            "quantity_bags": 50,
            "district_id": EJURA_DISTRICT_ID,
            "harvest_date": harvest_4wk,
            "source": "field_agent",
            "agent_id": 1,
        },
        {
            "farmer_id": farmer_id,
            "crop": "onion",
            "quantity_bags": 30,
            "district_id": EJURA_DISTRICT_ID,
            "harvest_date": harvest_5wk,
            "source": "field_agent",
            "agent_id": 1,
        },
        {
            "farmer_id": farmer_id,
            "crop": "rice",
            "quantity_bags": 20,
            "district_id": EJURA_DISTRICT_ID,
            "harvest_date": yesterday_str,
            "source": "field_agent",
            "agent_id": 1,
        },
    ]
}
r = requests.post(f"{BASE}/api/declarations/bulk", json=bulk_payload)
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 200:
    data = r.json()
    _check(
        data.get("success_count") == 2,
        "success_count = 2",
        f"got {data.get('success_count')}",
        f"expected 2, got {data.get('success_count')}",
    )
    _check(
        data.get("failed_count") == 1,
        "failed_count = 1",
        f"got {data.get('failed_count')}",
        f"expected 1, got {data.get('failed_count')}",
    )
    _check(
        len(data.get("declaration_ids", [])) == 2,
        "declaration_ids has 2 entries",
        str(data.get("declaration_ids")),
    )
    errors = data.get("errors", [])
    _check(len(errors) == 1, "errors has 1 entry", str(errors))
    if errors:
        _check(
            "reason" in errors[0],
            "error entry has reason field",
            errors[0].get("reason"),
        )
else:
    _fail("POST /api/declarations/bulk", f"status {r.status_code}: {r.text}")


# ── Summary ───────────────────────────────────────────────────────────────────

total = passed + failed
print(f"\n{'='*50}")
print(f"OVERALL: {passed}/{total} PASSED")
print(f"{'='*50}\n")

# Clean up temp lookup file if it still exists
import os, pathlib
tmp = pathlib.Path("_lookup_district.py")
if tmp.exists():
    tmp.unlink()

sys.exit(0 if failed == 0 else 1)
