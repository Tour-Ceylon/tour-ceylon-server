"""Provider-agnostic payment orchestration. Never imports a gateway adapter."""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Optional

from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.bookingInquiry import BookingInquiry
from app.models.enum import InquiryStatus, PaymentMethod, PaymentTransactionStatus
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
from app.payments.errors import PaymentError
from app.payments import links, pricing
from app.payments.models import Payment
from app.payments.registry import get_provider
from app.payments.repository import PaymentRepository

logger = logging.getLogger("app.payments")

# The team has accepted the request: stays may now be paid for.
APPROVED_INQUIRY_STATUSES = (InquiryStatus.QUOTED, InquiryStatus.CONVERTED_TO_BOOKING)


@dataclass
class PaidNotice:
    """Plain snapshot used by the confirmation email so the task needs no DB session."""

    booking_reference: str
    customer_name: str
    customer_email: str
    amount: Decimal
    currency: str
    order_id: str
    kind: str = TargetType.TRANSPORT_BOOKING.value


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

    def not_payable_reason(self, booking: TransportBooking, db: Session) -> Optional[str]:
        if booking.payment_status == "paid":
            return "This booking is already paid."
        if booking.booking_status in ("cancelled", "completed"):
            return f"This booking is {booking.booking_status} and cannot be paid."
        return None

    def amount_and_currency(self, booking: TransportBooking, db: Session):
        return _two_dp(booking.total_price), (booking.currency or "").upper()

    def customer_name(self, booking: TransportBooking) -> str:
        return booking.customer_name

    def customer_email(self, booking: TransportBooking) -> str:
        return booking.customer_email

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

    def apply_status(self, db: Session, booking: TransportBooking, status: PaymentStatus) -> None:
        if status == PaymentStatus.SUCCEEDED:
            booking.payment_status = "paid"
            if booking.booking_status == "pending":
                booking.booking_status = "confirmed"
        elif status == PaymentStatus.CHARGEDBACK:
            booking.payment_status = "chargedback"
        # pending / failed / cancelled leave the booking unpaid so the customer can retry.


class BookingInquiryTarget:
    """Cart checkout (stays, packages, safaris, experiences) paid online.

    The amount is rebuilt from database prices; the inquiry's own stored total
    is browser-supplied and is never charged.
    """

    target_type = TargetType.BOOKING_INQUIRY.value

    def load(self, db: Session, target_id) -> Optional[BookingInquiry]:
        return db.get(BookingInquiry, target_id)

    def authorize(
        self,
        inquiry: BookingInquiry,
        user: Optional[User],
        reference: Optional[str],
        email: Optional[str],
    ) -> bool:
        # Inquiries are created without sign-in, so reference + email is the proof.
        if not (reference and email):
            return False
        return (
            reference.strip().upper() == (inquiry.reference or "").upper()
            and email.strip().lower() == (inquiry.email or "").strip().lower()
        )

    def not_payable_reason(self, inquiry: BookingInquiry, db: Session) -> Optional[str]:
        if inquiry.status == InquiryStatus.CANCELLED:
            return "This booking request was cancelled and cannot be paid."
        # Stays are paid only after the team has confirmed the rooms (approve, then pay).
        if inquiry.status not in APPROVED_INQUIRY_STATUSES and pricing.contains_stay(db, inquiry.cart_items):
            return (
                "Stays are paid after our team confirms availability. "
                "We will email you a secure payment link as soon as your rooms are confirmed."
            )
        return None

    def amount_and_currency(self, inquiry: BookingInquiry, db: Session):
        priced = pricing.price_cart(db, inquiry.cart_items)
        return priced.amount, priced.currency

    def description(self, inquiry: BookingInquiry) -> str:
        titles = [str(i.get("title") or "") for i in (inquiry.cart_items or []) if isinstance(i, dict)]
        text = f"Booking {inquiry.reference}: " + ", ".join(t for t in titles if t)
        return text[:120]

    def customer(self, inquiry: BookingInquiry) -> CheckoutCustomer:
        return CheckoutCustomer(
            first_name=inquiry.first_name or "Customer",
            last_name=inquiry.last_name or "-",
            email=inquiry.email,
            phone=inquiry.phone or "",
            address="N/A",
            city="N/A",
            country=inquiry.nationality or "Sri Lanka",
        )

    def reference(self, inquiry: BookingInquiry) -> str:
        return inquiry.reference

    def customer_name(self, inquiry: BookingInquiry) -> str:
        return f"{inquiry.first_name} {inquiry.last_name}".strip()

    def customer_email(self, inquiry: BookingInquiry) -> str:
        return inquiry.email

    def apply_status(self, db: Session, inquiry: BookingInquiry, status: PaymentStatus) -> None:
        # The inquiry keeps its own workflow status; "paid" is read from the payments table.
        # The booking the approval created (stays) records the money too.
        booking = db.get(Booking, inquiry.booking_id) if getattr(inquiry, "booking_id", None) else None
        if booking is None:
            return
        if status == PaymentStatus.SUCCEEDED:
            booking.payment_method = PaymentMethod.ONLINE
            booking.payment_status = PaymentTransactionStatus.SUCCEEDED
        elif status == PaymentStatus.CHARGEDBACK:
            booking.payment_status = PaymentTransactionStatus.REFUNDED


_TARGETS = {
    TransportBookingTarget.target_type: TransportBookingTarget(),
    BookingInquiryTarget.target_type: BookingInquiryTarget(),
}


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
    expected_amount: Optional[Decimal] = None,
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

    return _start_payment(db, provider, target, target_type, obj, expected_amount)


def initiate_link_checkout(db: Session, token: str) -> tuple[Payment, CheckoutInstructions]:
    """Start a payment for an approved stay request from its emailed payment link."""
    try:
        provider = get_provider()
    except PaymentProviderError as exc:
        raise PaymentError(503, str(exc))

    inquiry = _inquiry_from_token(db, token)
    return _start_payment(db, provider, _get_target(TargetType.BOOKING_INQUIRY.value), TargetType.BOOKING_INQUIRY.value, inquiry, None)


def _inquiry_from_token(db: Session, token: str) -> BookingInquiry:
    inquiry = db.get(BookingInquiry, links.read_payment_token(token))
    if inquiry is None:
        raise PaymentError(404, "This payment link is not valid.")
    return inquiry


def get_link_summary(db: Session, token: str) -> dict:
    """What the pay page shows: the stay, the price and whether it can be paid right now."""
    inquiry = _inquiry_from_token(db, token)
    target = _get_target(TargetType.BOOKING_INQUIRY.value)
    summary = {
        "reference": inquiry.reference,
        "customer_name": target.customer_name(inquiry),
        "customer_email": inquiry.email,
        "state": "ready",
        "message": None,
        "amount": None,
        "currency": None,
        "subtotal": None,
        "taxes": None,
        "lines": [],
    }
    if PaymentRepository(db).has_succeeded_for_target(TargetType.BOOKING_INQUIRY.value, inquiry.id):
        return {**summary, "state": "paid", "message": "This booking has already been paid. Thank you!"}
    if inquiry.status == InquiryStatus.CANCELLED:
        return {**summary, "state": "cancelled", "message": "This booking request was cancelled."}
    reason = target.not_payable_reason(inquiry, db)
    if reason:
        return {**summary, "state": "not_approved", "message": reason}
    try:
        priced = pricing.price_cart(db, inquiry.cart_items)
    except PaymentError as exc:
        return {**summary, "state": "unavailable", "message": exc.detail}
    return {
        **summary,
        "amount": priced.amount,
        "currency": priced.currency,
        "subtotal": priced.subtotal,
        "taxes": priced.taxes,
        "lines": [
            {
                "title": line.title,
                "start": line.start,
                "end": line.end,
                "nights": line.nights,
                "rooms": line.rooms,
                "travelers": line.travelers,
                "total": line.total,
            }
            for line in priced.lines
        ],
    }


def _start_payment(db: Session, provider, target, target_type: str, obj, expected_amount: Optional[Decimal]):
    reason = target.not_payable_reason(obj, db)
    repo = PaymentRepository(db)
    if reason is None and repo.has_succeeded_for_target(target_type, obj.id):
        reason = "This booking is already paid."
    if reason:
        raise PaymentError(409, reason)

    amount, currency = target.amount_and_currency(obj, db)
    if expected_amount is not None and abs(_two_dp(expected_amount) - amount) > pricing.TOLERANCE:
        raise PaymentError(409, "The price has changed. Please review your booking and try again.")
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
        target.apply_status(db, obj, new)
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
            customer_name=target.customer_name(obj),
            customer_email=target.customer_email(obj),
            amount=_two_dp(payment.amount),
            currency=payment.currency,
            order_id=payment.order_id,
            kind=payment.target_type,
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
    if user is not None and getattr(obj, "user_id", None) is not None and obj.user_id == user.id:
        return True
    return bool(email) and email.strip().lower() == (target.customer_email(obj) or "").strip().lower()
