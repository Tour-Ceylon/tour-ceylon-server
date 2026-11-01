"""Provider-agnostic payment orchestration. Never imports a gateway adapter."""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Optional

from sqlalchemy.orm import Session

from app.models.transportBooking import TransportBooking
from app.models.user import User
from app.payments.base import (
    CheckoutCustomer,
    CheckoutInstructions,
    CheckoutRequest,
    NormalizedPaymentEvent,
    PaymentProviderError,
)
from app.payments.constants import FINAL_STATUSES, PaymentStatus, TargetType
from app.payments.models import Payment
from app.payments.registry import get_provider
from app.payments.repository import PaymentRepository

logger = logging.getLogger("app.payments")


class PaymentError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class PaidNotice:
    """Plain snapshot used by the confirmation email so the task needs no DB session."""

    booking_reference: str
    customer_name: str
    customer_email: str
    amount: Decimal
    currency: str
    order_id: str


@dataclass
class NotifyResult:
    http_status: int
    message: str
    paid_notice: Optional[PaidNotice] = None


def _two_dp(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


class TransportBookingTarget:
    """Adapter between a transport booking and the payment module."""

    target_type = TargetType.TRANSPORT_BOOKING.value

    def load(self, db: Session, target_id) -> Optional[TransportBooking]:
        return db.get(TransportBooking, target_id)

    def authorize(
        self,
        booking: TransportBooking,
        user: Optional[User],
        reference: Optional[str],
        email: Optional[str],
    ) -> bool:
        if user is not None and booking.user_id is not None and booking.user_id == user.id:
            return True
        # Guest bookings (and bookings created before sign-in): reference + email must match.
        if reference and email:
            return (
                reference.strip().upper() == (booking.booking_reference or "").upper()
                and email.strip().lower() == (booking.customer_email or "").strip().lower()
            )
        return False

    def not_payable_reason(self, booking: TransportBooking) -> Optional[str]:
        if booking.payment_status == "paid":
            return "This booking is already paid."
        if booking.booking_status in ("cancelled", "completed"):
            return f"This booking is {booking.booking_status} and cannot be paid."
        return None

    def amount_and_currency(self, booking: TransportBooking):
        return _two_dp(booking.total_price), (booking.currency or "").upper()

    def description(self, booking: TransportBooking) -> str:
        text = f"Transfer {booking.booking_reference}: {booking.pickup_location} to {booking.destination_location}"
        return text[:120]

    def customer(self, booking: TransportBooking) -> CheckoutCustomer:
        parts = (booking.customer_name or "").strip().split(" ", 1)
        return CheckoutCustomer(
            first_name=parts[0] or "Customer",
            last_name=parts[1] if len(parts) > 1 else "-",
            email=booking.customer_email,
            phone=booking.customer_phone or "",
            address=(booking.pickup_location or "N/A")[:100],
            city="N/A",
            country=booking.customer_country or "Sri Lanka",
        )

    def reference(self, booking: TransportBooking) -> str:
        return booking.booking_reference

    def apply_status(self, booking: TransportBooking, status: PaymentStatus) -> None:
        if status == PaymentStatus.SUCCEEDED:
            booking.payment_status = "paid"
            if booking.booking_status == "pending":
                booking.booking_status = "confirmed"
        elif status == PaymentStatus.CHARGEDBACK:
            booking.payment_status = "chargedback"
        # pending / failed / cancelled leave the booking unpaid so the customer can retry.


_TARGETS = {TransportBookingTarget.target_type: TransportBookingTarget()}


def _get_target(target_type: str):
    target = _TARGETS.get(target_type)
    if target is None:
        raise PaymentError(400, "Unsupported payment target")
    return target


def initiate_checkout(
    db: Session,
    *,
    target_type: str,
    target_id,
    user: Optional[User],
    booking_reference: Optional[str],
    customer_email: Optional[str],
) -> tuple[Payment, CheckoutInstructions]:
    try:
        provider = get_provider()
    except PaymentProviderError as exc:
        raise PaymentError(503, str(exc))

    target = _get_target(target_type)
    obj = target.load(db, target_id)
    # Same answer for "missing" and "not yours" so ids cannot be probed.
    if obj is None or not target.authorize(obj, user, booking_reference, customer_email):
        raise PaymentError(404, "Booking not found")

    reason = target.not_payable_reason(obj)
    repo = PaymentRepository(db)
    if reason is None and repo.has_succeeded_for_target(target_type, obj.id):
        reason = "This booking is already paid."
    if reason:
        raise PaymentError(409, reason)

    amount, currency = target.amount_and_currency(obj)
    order_id = f"TRT-{target.reference(obj)}-{uuid.uuid4().hex[:8]}"[:64]
    payment = repo.create(
        target_type=target_type,
        target_id=obj.id,
        provider=provider.name,
        order_id=order_id,
        amount=amount,
        currency=currency,
        status=PaymentStatus.INITIATED.value,
    )

    try:
        instructions = provider.create_checkout(
            CheckoutRequest(
                order_id=order_id,
                amount=amount,
                currency=currency,
                description=target.description(obj),
                customer=target.customer(obj),
                internal_reference=target.reference(obj),
                internal_payment_id=str(payment.id),
            )
        )
    except PaymentProviderError as exc:
        db.rollback()
        raise PaymentError(400, str(exc))

    db.commit()
    db.refresh(payment)
    return payment, instructions


def handle_notification(
    db: Session, raw_body: bytes, headers: Mapping[str, str]
) -> NotifyResult:
    provider = get_provider()
    event = provider.parse_and_verify_webhook(raw_body, headers)
    repo = PaymentRepository(db)

    payment = repo.get_by_order_id(event.order_id, lock=True) if event.order_id else None

    def audit() -> None:
        repo.add_event(
            payment_id=payment.id if payment else None,
            provider=provider.name,
            raw_payload=_redact(event.raw),
            signature_valid=event.signature_valid,
            status_code=event.status_code,
        )
        db.commit()

    if not event.signature_valid:
        audit()
        logger.warning("Rejected %s notification: invalid signature (order=%s)", provider.name, event.order_id)
        return NotifyResult(400, "invalid signature")

    if payment is None:
        audit()
        logger.warning("Rejected %s notification: unknown order %s", provider.name, event.order_id)
        return NotifyResult(400, "unknown order")

    if event.amount is None or _two_dp(event.amount) != _two_dp(payment.amount) or (
        (event.currency or "").upper() != payment.currency
    ):
        audit()
        logger.warning("Rejected notification for %s: amount/currency mismatch", payment.order_id)
        return NotifyResult(400, "amount mismatch")

    if event.status is None:
        audit()
        logger.warning("Rejected notification for %s: unknown status code", payment.order_id)
        return NotifyResult(400, "unknown status")

    current = PaymentStatus(payment.status)
    new = event.status

    # Idempotency: a final payment never changes, except a success can be charged back.
    if current in FINAL_STATUSES and not (
        current == PaymentStatus.SUCCEEDED and new == PaymentStatus.CHARGEDBACK
    ):
        audit()
        return NotifyResult(200, "already processed")
    if new == current:
        audit()
        return NotifyResult(200, "already processed")

    target = _get_target(payment.target_type)
    obj = target.load(db, payment.target_id)

    payment.status = new.value
    if event.provider_payment_id:
        payment.provider_payment_id = event.provider_payment_id
    if obj is not None:
        target.apply_status(obj, new)
    repo.add_event(
        payment_id=payment.id,
        provider=provider.name,
        raw_payload=_redact(event.raw),
        signature_valid=True,
        status_code=event.status_code,
    )
    db.commit()  # payment, booking and audit row land together

    notice = None
    if new == PaymentStatus.SUCCEEDED and obj is not None:
        notice = PaidNotice(
            booking_reference=target.reference(obj),
            customer_name=obj.customer_name,
            customer_email=obj.customer_email,
            amount=_two_dp(payment.amount),
            currency=payment.currency,
            order_id=payment.order_id,
        )
    return NotifyResult(200, "ok", notice)


def _redact(raw: dict) -> dict:
    """Keep the audit payload useful but drop anything signature-like we don't need."""
    return {k: v for k, v in raw.items() if k.lower() not in {"merchant_secret", "secret"}}


def can_view_payment(
    payment: Payment, db: Session, user: Optional[User], email: Optional[str]
) -> bool:
    if user is not None:
        role = getattr(user.role, "value", str(user.role)).upper()
        if role == "ADMIN":
            return True
    target = _TARGETS.get(payment.target_type)
    obj = target.load(db, payment.target_id) if target else None
    if obj is None:
        return False
    if user is not None and obj.user_id is not None and obj.user_id == user.id:
        return True
    return bool(email) and email.strip().lower() == (obj.customer_email or "").strip().lower()
