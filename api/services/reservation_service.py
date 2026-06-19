import logging
import random
from datetime import datetime, timezone

from fastapi import HTTPException

from api.payment_gateway import PaymentGateway
from db.connection import get_session
from db.repositories.declaration_repo import DeclarationRepo
from db.repositories.reservation_repo import ReservationRepo

logger = logging.getLogger(__name__)

# Bag-to-kilogram conversion used for availability and pricing.
# Adjust if a crop uses a non-standard bag size.
BAG_KG = 100


def _generate_ref() -> str:
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rnd = random.randint(1000, 9999)
    return f"AGM-{ts}-{rnd}"


class ReservationService:

    @staticmethod
    def create(
        declaration_id: int,
        buyer_phone: str,
        buyer_name: str,
        quantity_bags: int,
        momo_phone: str,
        gateway: PaymentGateway,
    ) -> dict:
        # `reference` doubles as the payment idempotency key. Generating it once
        # at the top means client retries that re-send the same reference will
        # not produce a second charge when the gateway is idempotency-aware.
        reference = _generate_ref()

        # Pre-fetch price without a row lock so we can pass a real amount to the
        # payment gateway before acquiring the lock. The amount stored in the DB
        # is always recomputed from the locked row, so a price change between
        # these two reads is caught and only the locked value is persisted.
        with get_session() as db:
            preview = DeclarationRepo.get_price(db, declaration_id)
        if preview is None:
            raise HTTPException(status_code=404, detail="Listing not found or no longer active")

        unit_price_preview = float(preview.price_forecast_ghs or 0.0) * BAG_KG
        amount_preview     = round(unit_price_preview * quantity_bags, 2)

        # Charge before acquiring the DB row lock so we never hold a lock
        # during a network call. `reference` is the idempotency key: if this
        # request is retried the gateway returns the original result without a
        # second debit.
        charge = gateway.charge(momo_phone, amount=amount_preview, idempotency_key=reference)
        if not charge.success:
            return {
                "status":         "failed",
                "reservation_id": None,
                "reference":      reference,
                "provider":       charge.provider,
                "amount_ghs":     None,
                "message":        charge.message,
            }

        # Single session: lock the declaration row so concurrent requests cannot
        # double-book the same bags. If anything here raises, the DB transaction
        # rolls back automatically. We then attempt a refund so the customer is
        # not charged for a reservation that was never created.
        try:
            with get_session() as db:
                decl = DeclarationRepo.lock_active(db, declaration_id)
                if not decl:
                    raise HTTPException(
                        status_code=404,
                        detail="Listing not found or no longer active",
                    )

                reserved_bags = DeclarationRepo.reserved_bags(db, declaration_id)
                total_bags    = int(decl.quantity_kg / BAG_KG)
                available     = total_bags - reserved_bags

                if quantity_bags > available:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Only {available} bag{'s' if available != 1 else ''} available "
                            f"({reserved_bags} already reserved out of {total_bags})."
                        ),
                    )

                unit_price = float(decl.price_forecast_ghs or 0.0) * BAG_KG
                total      = round(unit_price * quantity_bags, 2)

                # Both writes in the same transaction: if payment insert fails,
                # the reservation row is rolled back automatically.
                reservation_id = ReservationRepo.insert_reservation(
                    db, declaration_id, buyer_phone, buyer_name, quantity_bags, unit_price, total
                )
                ReservationRepo.insert_payment(
                    db, reservation_id, charge.provider, momo_phone, total, reference
                )

        except Exception as exc:
            # The gateway charged the customer but the DB write failed (validation
            # error, DB unavailability, etc.). Attempt a refund so the customer is
            # not debited for a reservation that does not exist.
            refund = gateway.refund(reference)
            logger.error(
                "DB failure after successful charge; refund=%s ref=%s err=%s",
                refund.success, reference, exc,
            )
            raise

        return {
            "status":         "success",
            "reservation_id": reservation_id,
            "reference":      reference,
            "provider":       charge.provider,
            "amount_ghs":     total,
            "message":        charge.message,
        }
