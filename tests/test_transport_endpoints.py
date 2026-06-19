"""
Live integration tests for transport API endpoints.
Requires the server to be running at http://localhost:8000.

Usage:
    python tests/test_transport_endpoints.py
"""

import sys

import requests

BASE = "http://localhost:8000"
EJURA_DISTRICT_ID = 32       # pickup district (Ashanti region)
ASHANTI_DEST_ID = 7          # Adansi Akrofuom, Ashanti region (destination)
VALID_PHONE = "0201234567"   # unique enough to avoid clashes

passed = 0
failed = 0
provider_id = None


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


# ── Test 1: Register a transport provider ─────────────────────────────────────

print("\n[Test 1] Register transport provider")
r = requests.post(f"{BASE}/api/transport/register", json={
    "full_name": "Kwame Asante",
    "phone_number": VALID_PHONE,
    "business_name": "Asante Logistics",
    "district_id": EJURA_DISTRICT_ID,
    "truck_capacity_kg": 5000.0,
    "truck_count": 2,
    "vehicle_type": "medium_truck",
    "service_regions": [],    # empty = serves all regions
    "base_rate_per_km": 3.50,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 201:
    data = r.json()
    provider_id = data.get("provider_id")
    _check(provider_id is not None, "provider_id returned", f"id={provider_id}")
    _check(data.get("vehicle_type") == "medium_truck", "vehicle_type correct")
    _check(data.get("truck_capacity_kg") == 5000.0, "truck_capacity_kg correct")
    _check(data.get("district_name") == "Ejura-Sekyedumase", "district_name correct", data.get("district_name"))
    _check(data.get("message") == "registered successfully", "message correct")
elif r.status_code == 409:
    data = r.json()
    provider_id = data.get("detail", {}).get("existing_provider_id")
    print(f"  NOTE: provider already exists (id={provider_id}), continuing with existing id")
    _ok("provider_id returned (pre-existing)", f"id={provider_id}")
else:
    _fail("POST /api/transport/register", f"unexpected status {r.status_code}: {r.text}")


# ── Test 2: Duplicate phone (expect 409) ──────────────────────────────────────

print("\n[Test 2] Register with same phone (expect 409)")
r = requests.post(f"{BASE}/api/transport/register", json={
    "full_name": "Another Person",
    "phone_number": VALID_PHONE,
    "district_id": EJURA_DISTRICT_ID,
    "truck_capacity_kg": 5000.0,
    "vehicle_type": "medium_truck",
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 409, "status 409 for duplicate phone", f"got {r.status_code}")
if r.status_code == 409:
    detail = r.json().get("detail", {})
    _check(detail.get("error") == "phone_already_registered", "error key correct")
    _check(detail.get("existing_provider_id") == provider_id, "existing_provider_id matches")


# ── Test 3: Invalid vehicle type (expect 400) ─────────────────────────────────

print("\n[Test 3] Invalid vehicle_type (expect 400)")
r = requests.post(f"{BASE}/api/transport/register", json={
    "full_name": "Test Provider",
    "phone_number": "0209999999",
    "district_id": EJURA_DISTRICT_ID,
    "truck_capacity_kg": 5000.0,
    "vehicle_type": "bicycle",
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 400, "status 400 for invalid vehicle_type", f"got {r.status_code}")
if r.status_code == 400:
    detail = r.json().get("detail", "")
    _check("vehicle_type" in detail, "error mentions vehicle_type", detail)


# ── Test 4: Capacity out of range for vehicle type (expect 400) ───────────────

print("\n[Test 4] Capacity out of range for vehicle_type (expect 400)")
r = requests.post(f"{BASE}/api/transport/register", json={
    "full_name": "Test Provider",
    "phone_number": "0208888888",
    "district_id": EJURA_DISTRICT_ID,
    "truck_capacity_kg": 100.0,   # too small for any vehicle type
    "vehicle_type": "pickup",
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 400, "status 400 for out-of-range capacity", f"got {r.status_code}")
if r.status_code == 400:
    detail = r.json().get("detail", "")
    _check("truck_capacity_kg" in detail, "error mentions truck_capacity_kg", detail)


# ── Test 5: Invalid district (expect 400) ─────────────────────────────────────

print("\n[Test 5] Invalid district_id (expect 400)")
r = requests.post(f"{BASE}/api/transport/register", json={
    "full_name": "Test Provider",
    "phone_number": "0207777777",
    "district_id": 99999,
    "truck_capacity_kg": 5000.0,
    "vehicle_type": "medium_truck",
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 400, "status 400 for invalid district", f"got {r.status_code}")


# ── Test 6: Available transport - basic query ─────────────────────────────────

print("\n[Test 6] GET /api/transport/available (basic query)")
r = requests.get(f"{BASE}/api/transport/available", params={
    "district_id": EJURA_DISTRICT_ID,
    "cargo_kg": 500.0,
    "destination_district_id": ASHANTI_DEST_ID,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 200:
    data = r.json()
    _check(isinstance(data, list), "response is a list", f"{len(data)} providers")
    if data:
        first = data[0]
        required_fields = [
            "provider_id", "full_name", "phone_number", "vehicle_type",
            "truck_capacity_kg", "truck_count", "rating", "total_jobs",
            "base_district", "dist_from_base_km", "route_km",
        ]
        for field in required_fields:
            _check(field in first, f"field '{field}' present")
        _check(first.get("truck_capacity_kg", 0) >= 500.0, "capacity >= cargo_kg")
        _check(first.get("route_km", 0) > 0, "route_km > 0", f"{first.get('route_km')} km")
else:
    _fail("GET /api/transport/available", f"status {r.status_code}: {r.text}")


# ── Test 7: Available transport - cargo exceeds capacity ──────────────────────

print("\n[Test 7] GET /api/transport/available with very large cargo_kg")
r = requests.get(f"{BASE}/api/transport/available", params={
    "district_id": EJURA_DISTRICT_ID,
    "cargo_kg": 999_999.0,
    "destination_district_id": ASHANTI_DEST_ID,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code == 200:
    data = r.json()
    _check(isinstance(data, list), "response is a list (may be empty)", f"{len(data)} providers")
    _check(len(data) == 0, "no providers match impossibly large cargo", f"got {len(data)}")
else:
    _fail("GET /api/transport/available (large cargo)", f"status {r.status_code}: {r.text}")


# ── Test 8: Invalid pickup district ───────────────────────────────────────────

print("\n[Test 8] GET /api/transport/available with invalid pickup district")
r = requests.get(f"{BASE}/api/transport/available", params={
    "district_id": 99999,
    "cargo_kg": 1000.0,
    "destination_district_id": ASHANTI_DEST_ID,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 400, "status 400 for invalid pickup district", f"got {r.status_code}")


# ── Test 9: Invalid destination district ──────────────────────────────────────

print("\n[Test 9] GET /api/transport/available with invalid destination district")
r = requests.get(f"{BASE}/api/transport/available", params={
    "district_id": EJURA_DISTRICT_ID,
    "cargo_kg": 1000.0,
    "destination_district_id": 99999,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
_check(r.status_code == 400, "status 400 for invalid destination district", f"got {r.status_code}")


# ── Test 10: Register small pickup truck and verify range filtering ────────────

print("\n[Test 10] Register pickup truck and verify capacity filtering")
r = requests.post(f"{BASE}/api/transport/register", json={
    "full_name": "Adjoa Pickup",
    "phone_number": "0246543210",
    "district_id": EJURA_DISTRICT_ID,
    "truck_capacity_kg": 800.0,
    "vehicle_type": "pickup",
    "base_rate_per_km": 2.00,
})
print(f"  Status: {r.status_code}  Body: {r.json()}")
if r.status_code in (201, 409):
    # Query for cargo that exceeds pickup capacity but should return medium_truck
    r2 = requests.get(f"{BASE}/api/transport/available", params={
        "district_id": EJURA_DISTRICT_ID,
        "cargo_kg": 2000.0,
        "destination_district_id": ASHANTI_DEST_ID,
    })
    if r2.status_code == 200:
        data2 = r2.json()
        vehicle_types = [p.get("vehicle_type") for p in data2]
        _check(
            "pickup" not in vehicle_types,
            "pickup truck not returned for 2000 kg cargo",
            f"types: {vehicle_types}",
        )
    else:
        _fail("GET /api/transport/available (capacity filter)", f"status {r2.status_code}")
else:
    _fail("POST /api/transport/register (pickup)", f"status {r.status_code}: {r.text}")


# ── Summary ───────────────────────────────────────────────────────────────────

total = passed + failed
print(f"\n{'='*50}")
print(f"OVERALL: {passed}/{total} PASSED")
print(f"{'='*50}\n")

sys.exit(0 if failed == 0 else 1)
