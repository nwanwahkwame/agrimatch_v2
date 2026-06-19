"""Unit tests for PaymentGateway implementations."""

from api.payment_gateway import ChargeResult, SimulatedGateway


def _gateway() -> SimulatedGateway:
    gw = SimulatedGateway()
    gw._FAILURE_RATE = 0.0  # force success in all tests
    return gw


def test_charge_returns_charge_result():
    gw = _gateway()
    result = gw.charge("0244000001", amount=500.0, idempotency_key="AGM-001")
    assert isinstance(result, ChargeResult)
    assert result.success is True
    assert result.provider == "MTN MoMo"


def test_idempotent_charge_returns_same_result():
    gw = _gateway()
    first  = gw.charge("0244000001", amount=500.0, idempotency_key="AGM-001")
    second = gw.charge("0244000001", amount=500.0, idempotency_key="AGM-001")
    assert first is second  # exact same object, not a second charge


def test_different_keys_are_independent():
    gw = _gateway()
    r1 = gw.charge("0244000001", amount=100.0, idempotency_key="AGM-001")
    r2 = gw.charge("0244000001", amount=200.0, idempotency_key="AGM-002")
    assert r1 is not r2


def test_refund_succeeds_for_charged_key():
    gw = _gateway()
    gw.charge("0244000001", amount=500.0, idempotency_key="AGM-001")
    result = gw.refund("AGM-001")
    assert result.success is True


def test_refund_unknown_key_returns_failure():
    gw = _gateway()
    result = gw.refund("AGM-NONEXISTENT")
    assert result.success is False


def test_refund_clears_charge_so_key_is_reusable():
    gw = _gateway()
    gw.charge("0244000001", amount=500.0, idempotency_key="AGM-001")
    gw.refund("AGM-001")
    # After a refund the key slot is cleared; a retry produces a fresh charge.
    retry = gw.charge("0244000001", amount=500.0, idempotency_key="AGM-001")
    assert retry.success is True


def test_provider_detection_mtn():
    gw = _gateway()
    r = gw.charge("0244000001", 0, "k1")
    assert r.provider == "MTN MoMo"


def test_provider_detection_vodafone():
    gw = _gateway()
    r = gw.charge("0200000001", 0, "k2")
    assert r.provider == "Vodafone Cash"


def test_provider_detection_airteltigo():
    gw = _gateway()
    r = gw.charge("0270000001", 0, "k3")
    assert r.provider == "AirtelTigo Money"


def test_failure_rate_respected():
    gw = SimulatedGateway()
    gw._FAILURE_RATE = 1.0  # force all failures
    r = gw.charge("0244000001", 100.0, "AGM-fail")
    assert r.success is False
