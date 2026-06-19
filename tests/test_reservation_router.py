"""HTTP-layer tests for the reservation router.

Uses FastAPI TestClient with mocked service and repo calls so no DB is needed.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.reservations import router
from api.payment_gateway import SimulatedGateway

# Build a minimal app that only has the reservation router and bypasses auth.
app = FastAPI()
app.include_router(router)

# Bypass require_internal and inject a stub gateway for all tests in this module.
from api import security as _sec
from api import dependencies as _deps
app.dependency_overrides[_sec.require_internal]   = lambda: None
app.dependency_overrides[_deps.get_payment_gateway] = lambda: SimulatedGateway()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# ── POST /api/reservations ────────────────────────────────────────────────────

_VALID_PAYLOAD = {
    "declaration_id": 1,
    "buyer_phone":    "0244123456",
    "buyer_name":     "Kwame Adu",
    "quantity_bags":  5,
    "momo_phone":     "0244123456",
}

_SUCCESS_RESULT = {
    "status":         "success",
    "reservation_id": 42,
    "amount_ghs":     2500.0,
    "provider":       "MTN MoMo",
    "reference":      "AGM-TEST-001",
    "message":        "Payment confirmed.",
}


@patch("api.routers.reservations.ReservationService.create", return_value=_SUCCESS_RESULT)
def test_create_reservation_returns_201(mock_create, client):
    resp = client.post("/api/reservations", json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    assert resp.json()["status"] == "success"
    assert resp.json()["reservation_id"] == 42
    mock_create.assert_called_once()


@patch("api.routers.reservations.ReservationService.create", return_value=_SUCCESS_RESULT)
def test_create_reservation_passes_correct_args(mock_create, client):
    client.post("/api/reservations", json=_VALID_PAYLOAD)
    _, kwargs = mock_create.call_args
    assert kwargs["declaration_id"] == 1
    assert kwargs["buyer_phone"]    == "0244123456"
    assert kwargs["quantity_bags"]  == 5


def test_create_reservation_rejects_invalid_phone(client):
    bad = {**_VALID_PAYLOAD, "buyer_phone": "12345"}
    resp = client.post("/api/reservations", json=bad)
    assert resp.status_code == 422


def test_create_reservation_rejects_zero_bags(client):
    bad = {**_VALID_PAYLOAD, "quantity_bags": 0}
    resp = client.post("/api/reservations", json=bad)
    assert resp.status_code == 422


def test_create_reservation_rejects_name_too_long(client):
    bad = {**_VALID_PAYLOAD, "buyer_name": "A" * 121}
    resp = client.post("/api/reservations", json=bad)
    assert resp.status_code == 422


def test_create_reservation_rejects_negative_declaration_id(client):
    bad = {**_VALID_PAYLOAD, "declaration_id": -1}
    resp = client.post("/api/reservations", json=bad)
    assert resp.status_code == 422


# ── GET /api/reservations/buyer/{phone} ───────────────────────────────────────

_MOCK_ROW = MagicMock()
_MOCK_ROW.id             = 1
_MOCK_ROW.declaration_id = 10
_MOCK_ROW.crop           = "Maize"
_MOCK_ROW.district_name  = "Kumasi"
_MOCK_ROW.region_name    = "Ashanti"
_MOCK_ROW.quantity_bags  = 5
_MOCK_ROW.total_ghs      = 2500.0
_MOCK_ROW.status         = "confirmed"
_MOCK_ROW.created_at     = MagicMock(isoformat=lambda: "2026-06-17T12:00:00")
_MOCK_ROW.reference      = "AGM-TEST-001"
_MOCK_ROW.provider       = "MTN MoMo"


@patch("api.routers.reservations.ReservationRepo.get_buyer_reservations", return_value=[_MOCK_ROW])
@patch("api.routers.reservations.get_session")
def test_buyer_reservations_returns_list(mock_gs, mock_repo, client):
    from contextlib import contextmanager

    @contextmanager
    def _fake():
        yield MagicMock()

    mock_gs.side_effect = _fake

    resp = client.get("/api/reservations/buyer/0244123456")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["crop"] == "Maize"
    assert data[0]["status"] == "confirmed"
