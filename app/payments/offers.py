"""The "pay for your confirmed stay" offer a guest receives after the team approves a request."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.bookingInquiry import BookingInquiry
from app.payments import links, pricing
from app.payments.constants import TargetType
from app.payments.errors import PaymentError
from app.payments.repository import PaymentRepository

# Imported lazily by callers that already depend on payments.service; kept here as plain values
# to avoid a circular import (service imports links and pricing).
from app.models.enum import InquiryStatus

APPROVED = (InquiryStatus.QUOTED, InquiryStatus.CONVERTED_TO_BOOKING)


@dataclass(frozen=True)
class PaymentOffer:
    url: str
    expires_at: datetime
    amount: Decimal
    currency: str
    subtotal: Decimal
    taxes: Decimal
    lines: List[pricing.PricedLine]


def build_inquiry_offer(db: Session, inquiry: BookingInquiry) -> Optional[PaymentOffer]:
    """A pay link for an approved stay request, or None when there is nothing to pay online.

    None means: payments are off, the request is not approved or already paid, it has no stay
    in it, or the server cannot verify the price.
    """
    if not (settings.PAYMENT_PROVIDER or "").strip():
        return None
    if inquiry.status not in APPROVED:
        return None
    if not pricing.contains_stay(db, inquiry.cart_items):
        return None
    if PaymentRepository(db).has_succeeded_for_target(TargetType.BOOKING_INQUIRY.value, inquiry.id):
        return None
    try:
        priced = pricing.price_cart(db, inquiry.cart_items)
    except PaymentError:
        return None

    token, expires_at = links.create_payment_token(inquiry.id)
    return PaymentOffer(
        url=links.payment_url(token),
        expires_at=expires_at,
        amount=priced.amount,
        currency=priced.currency,
        subtotal=priced.subtotal,
        taxes=priced.taxes,
        lines=priced.lines,
    )
