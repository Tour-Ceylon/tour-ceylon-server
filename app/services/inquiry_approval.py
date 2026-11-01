"""What the guest is told when the team approves a booking request."""
import logging

from sqlalchemy.orm import Session

from app.integrations.email_provider import email_provider
from app.models.bookingInquiry import BookingInquiry
from app.payments.offers import build_inquiry_offer
from app.services.booking_inquiry_service import BookingInquiryService

logger = logging.getLogger("app.inquiry_approval")


def notify_inquiry_approved(db: Session, inquiry: BookingInquiry) -> bool:
    """Email the guest after approval.

    A stay gets one email with the confirmed price and a secure pay link. Anything else (or when
    online payment is off) gets the usual "booking confirmed" email.
    """
    detailed = BookingInquiryService(db).get_inquiry_by_id(inquiry.id)
    if detailed is None:
        return False

    offer = build_inquiry_offer(db, inquiry)
    if offer is not None:
        logger.info("Sending stay payment request for %s", inquiry.reference)
        return email_provider.send_stay_payment_request(detailed, offer)
    return email_provider.send_vendor_booking_accepted_email(detailed)
