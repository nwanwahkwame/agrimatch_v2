"""Unit tests for ReservationService business logic."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.payment_gateway import ChargeResult, PaymentGateway
from api.services.reservation_service import ReservationService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gateway(success: bool = True, provider: str = "MTN MoMo") -> MagicMock:
    gw = MagicMock(spec=PaymentGateway)
    msg = (
        "Payment confirmed. Farmer will contact you within 24 hours."
        if success
        else "Payment declined by your network. Please try again."
    )
    gw.charge.return_value = ChargeResult(success=success, provider=provider, message=msg)
    gw.refund.return_value = MagicMock(success=True, message="Refund issued.")
    return gw


def _decl(quantity_kg: float = 1000.0, price_forecast_ghs: float = 5.0):
    d = MagicMock()
    d.quantity_kg        = quantity_kg
    d.price_forecast_ghs = price_forecast_ghs
    return d


@contextmanager
def _fake_session(mock_db):
    yield mock_db


# ── Tests: payment failure ────────────────────────────────────────────────────

@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_payment_declined_returns_failed_status(mock_gs, mock_lock):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    gw = _gateway(success=False)

    result = ReservationService.create(
        declaration_id=1,
        buyer_phone="0244000001",
        buyer_name="Kwame",
        quantity_bags=5,
        momo_phone="0244000001",
        gateway=gw,
    )

    assert result["status"] == "failed"
    assert result["reservation_id"] is None
    assert result["amount_ghs"] is None
    # Pre-fetch happened (1 session), but the row lock and refund must not be called.
    mock_lock.assert_not_called()
    gw.refund.assert_not_called()
    assert mock_gs.call_count == 1


# ── Tests: listing not found ──────────────────────────────────────────────────

@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_listing_not_found_raises_404(mock_gs, mock_lock):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_lock.return_value = None
    gw = _gateway()

    with pytest.raises(HTTPException) as exc:
        ReservationService.create(
            declaration_id=999,
            buyer_phone="0244000001",
            buyer_name="Kwame",
            quantity_bags=1,
            momo_phone="0244000001",
            gateway=gw,
        )
    assert exc.value.status_code == 404
    # Listing was not found after charging -- customer must be refunded.
    gw.refund.assert_called_once()


# ── Tests: insufficient bags ──────────────────────────────────────────────────

@patch("api.services.reservation_service.DeclarationRepo.reserved_bags")
@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_overbooking_raises_400(mock_gs, mock_lock, mock_reserved):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_lock.return_value = _decl(quantity_kg=500.0)   # 5 bags total
    mock_reserved.return_value = 4                       # 4 already reserved
    gw = _gateway()

    with pytest.raises(HTTPException) as exc:
        ReservationService.create(
            declaration_id=1,
            buyer_phone="0244000001",
            buyer_name="Kwame",
            quantity_bags=2,   # requesting 2, only 1 left
            momo_phone="0244000001",
            gateway=gw,
        )
    assert exc.value.status_code == 400
    assert "1 bag" in exc.value.detail
    # Customer was charged but reservation cannot be completed -- must refund.
    gw.refund.assert_called_once()


# ── Tests: DB failure triggers compensation refund ────────────────────────────

@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_db_failure_after_charge_triggers_refund(mock_gs, mock_lock):
    """If the DB session fails after a successful charge, the service must
    attempt a refund and re-raise the original exception."""
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_lock.side_effect = RuntimeError("DB connection lost")
    gw = _gateway(success=True)

    with pytest.raises(RuntimeError, match="DB connection lost"):
        ReservationService.create(
            declaration_id=1,
            buyer_phone="0244000001",
            buyer_name="Kwame",
            quantity_bags=1,
            momo_phone="0244000001",
            gateway=gw,
        )

    # Gateway was charged, then DB failed -- refund must be attempted.
    gw.charge.assert_called_once()
    gw.refund.assert_called_once()


# ── Tests: happy path ─────────────────────────────────────────────────────────

@patch("api.services.reservation_service.ReservationRepo.insert_payment")
@patch("api.services.reservation_service.ReservationRepo.insert_reservation")
@patch("api.services.reservation_service.DeclarationRepo.reserved_bags")
@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_success_returns_correct_total(mock_gs, mock_lock, mock_reserved, mock_ins_res, mock_ins_pay):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_lock.return_value = _decl(quantity_kg=1000.0, price_forecast_ghs=5.0)
    mock_reserved.return_value = 0
    mock_ins_res.return_value = 42
    gw = _gateway(provider="Vodafone Cash")

    result = ReservationService.create(
        declaration_id=1,
        buyer_phone="0244000001",
        buyer_name="Kwame",
        quantity_bags=5,
        momo_phone="0244000001",
        gateway=gw,
    )

    # 5 bags x (5.0 GHS/kg x 100 kg/bag) = 2500 GHS
    assert result["status"] == "success"
    assert result["reservation_id"] == 42
    assert result["amount_ghs"] == 2500.0
    assert result["provider"] == "Vodafone Cash"
    mock_ins_pay.assert_called_once()
    gw.refund.assert_not_called()


@patch("api.services.reservation_service.ReservationRepo.insert_payment")
@patch("api.services.reservation_service.ReservationRepo.insert_reservation")
@patch("api.services.reservation_service.DeclarationRepo.reserved_bags")
@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_reference_format(mock_gs, mock_lock, mock_reserved, mock_ins_res, mock_ins_pay):
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_lock.return_value = _decl()
    mock_reserved.return_value = 0
    mock_ins_res.return_value = 1
    gw = _gateway()

    result = ReservationService.create(1, "0244000001", "", 1, "0244000001", gw)

    assert result["reference"].startswith("AGM-")
    assert len(result["reference"]) > 10


@patch("api.services.reservation_service.ReservationRepo.insert_payment")
@patch("api.services.reservation_service.ReservationRepo.insert_reservation")
@patch("api.services.reservation_service.DeclarationRepo.reserved_bags")
@patch("api.services.reservation_service.DeclarationRepo.lock_active")
@patch("api.services.reservation_service.get_session")
def test_idempotency_key_is_reference(mock_gs, mock_lock, mock_reserved, mock_ins_res, mock_ins_pay):
    """The reference returned in the response must be the idempotency key
    passed to gateway.charge so a client retry uses the same key."""
    mock_db = MagicMock()
    mock_gs.side_effect = lambda: _fake_session(mock_db)
    mock_lock.return_value = _decl()
    mock_reserved.return_value = 0
    mock_ins_res.return_value = 1
    gw = _gateway()

    result = ReservationService.create(1, "0244000001", "", 1, "0244000001", gw)

    _, charge_kwargs = gw.charge.call_args
    assert charge_kwargs["idempotency_key"] == result["reference"]
