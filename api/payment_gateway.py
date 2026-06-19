import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


def _detect_provider(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    prefix = digits[1:4] if digits.startswith("0") else digits[3:6]
    if prefix[:2] in ("24", "54", "55", "59"):
        return "MTN MoMo"
    if prefix[:2] in ("20", "50"):
        return "Vodafone Cash"
    if prefix[:2] in ("27", "57", "26", "56"):
        return "AirtelTigo Money"
    return "Mobile Money"


@dataclass
class ChargeResult:
    success: bool
    provider: str
    message: str


@dataclass
class RefundResult:
    success: bool
    message: str


class PaymentGateway(ABC):

    @abstractmethod
    def charge(self, phone: str, amount: float, idempotency_key: str) -> ChargeResult:
        """Debit `amount` from `phone`. `idempotency_key` must be unique per intent;
        re-submitting the same key returns the original result without a second charge."""
        ...

    @abstractmethod
    def refund(self, idempotency_key: str) -> RefundResult:
        """Reverse a previously successful charge identified by `idempotency_key`."""
        ...


class SimulatedGateway(PaymentGateway):
    """Stub payment gateway for development and demo.

    Replace with a real provider SDK (e.g. Flutterwave, Paystack) in production.
    Pre-authorization happens before DB lock acquisition; a real gateway would use
    a two-phase auth/capture flow and honour the idempotency_key to prevent
    double-charges on client retries.
    """

    _FAILURE_RATE = 0.10

    def __init__(self) -> None:
        # Tracks charged keys so refund() and idempotent retries work in simulation.
        self._charges: dict[str, ChargeResult] = {}

    def charge(self, phone: str, amount: float, idempotency_key: str) -> ChargeResult:
        if idempotency_key in self._charges:
            return self._charges[idempotency_key]
        provider = _detect_provider(phone)
        if random.random() < self._FAILURE_RATE:
            result = ChargeResult(
                success=False,
                provider=provider,
                message="Payment declined by your network. Please try again.",
            )
        else:
            result = ChargeResult(
                success=True,
                provider=provider,
                message="Payment confirmed. Farmer will contact you within 24 hours.",
            )
        self._charges[idempotency_key] = result
        return result

    def refund(self, idempotency_key: str) -> RefundResult:
        original = self._charges.pop(idempotency_key, None)
        if original is None or not original.success:
            return RefundResult(success=False, message="No charge found to refund.")
        return RefundResult(success=True, message="Refund issued successfully.")
