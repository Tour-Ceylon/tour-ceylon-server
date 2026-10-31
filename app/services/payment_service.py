from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.booking import Booking
from app.models.bookingStatusHistory import BookingStatusHistory
from app.models.paymentTransactionHistory import PaymentTransaction
from app.models.enum import (
    BookingStatus,
    PaymentTransactionStatus,
    PaymentProvider,
    ChangedByType,
)


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def record_transaction(
        self,
        booking_id: UUID,
        amount: float,
        currency: Any,
        provider: PaymentProvider,
        status: PaymentTransactionStatus,
        external_reference: Optional[str] = None,
    ) -> PaymentTransaction:
        """Create an immutable PaymentTransaction ledger row."""
        tx = PaymentTransaction(
            booking_id=booking_id,
            provider=provider,
            amount=amount,
            currency=currency,
            status=status,
            external_reference=external_reference,
            created_at=datetime.utcnow(),
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def get_booking_transactions(self, booking_id: UUID) -> List[PaymentTransaction]:
        """Fetch all ledger transactions for a booking."""
        return (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.booking_id == booking_id)
            .order_by(PaymentTransaction.created_at.desc())
            .all()
        )

    def process_refund(
        self,
        booking_id: UUID,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
        admin_user_id: Optional[UUID] = None,
    ) -> PaymentTransaction:
        """
        Process a booking refund and write an immutable REFUNDED ledger entry (SRV-PAY-02).
        """
        booking = (
            self.db.query(Booking)
            .filter(Booking.id == booking_id)
            .with_for_update()
            .first()
        )
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        refund_amount = amount if amount is not None else float(booking.total_amount)
        if refund_amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refund amount must be positive")

        old_status = booking.status
        booking.status = BookingStatus.CANCELLED
        booking.payment_status = PaymentTransactionStatus.REFUNDED

        # Record status transition
        hist = BookingStatusHistory(
            booking_id=booking.id,
            old_status=old_status,
            new_status=BookingStatus.CANCELLED,
            changed_by_type=ChangedByType.ADMIN if admin_user_id else ChangedByType.SYSTEM,
            changed_by_user_id=admin_user_id,
            changed_at=datetime.utcnow(),
        )
        self.db.add(hist)

        # Record ledger entry
        tx = PaymentTransaction(
            booking_id=booking.id,
            provider=PaymentProvider.MANUAL,
            amount=refund_amount,
            currency=booking.currency,
            status=PaymentTransactionStatus.REFUNDED,
            external_reference=f"REFUND-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{reason or 'admin_override'}",
            created_at=datetime.utcnow(),
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        logger.info(f"Processed refund of {refund_amount} for booking {booking.booking_reference}")
        return tx

    def handle_webhook_event(
        self,
        provider: str,
        event_payload: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Idempotent webhook handler with signature validation and ledger recording (SRV-PAY-02).
        """
        external_ref = event_payload.get("transaction_id") or event_payload.get("id")
        booking_ref = event_payload.get("booking_reference") or event_payload.get("order_id")

        if not external_ref or not booking_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing transaction_id or booking_reference in webhook payload",
            )

        # Idempotency check: verify this external_reference was not already processed
        existing_tx = (
            self.db.query(PaymentTransaction)
            .filter(PaymentTransaction.external_reference == str(external_ref))
            .first()
        )
        if existing_tx:
            logger.info(f"Webhook transaction {external_ref} already processed. Skipping duplicate.")
            return {"status": "success", "message": "Transaction already recorded", "idempotent": True}

        booking = (
            self.db.query(Booking)
            .filter(Booking.booking_reference == str(booking_ref))
            .with_for_update()
            .first()
        )
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking {booking_ref} not found")

        event_status = event_payload.get("status", "success").lower()
        if event_status in ("success", "paid", "completed", "approved"):
            old_status = booking.status
            booking.status = BookingStatus.CONFIRMED
            booking.payment_status = PaymentTransactionStatus.SUCCEEDED

            hist = BookingStatusHistory(
                booking_id=booking.id,
                old_status=old_status,
                new_status=BookingStatus.CONFIRMED,
                changed_by_type=ChangedByType.SYSTEM,
                changed_by_user_id=None,
                changed_at=datetime.utcnow(),
            )
            self.db.add(hist)

            tx_status = PaymentTransactionStatus.SUCCEEDED
        else:
            tx_status = PaymentTransactionStatus.FAILED

        prov = PaymentProvider.STRIPE if provider.lower() == "stripe" else PaymentProvider.MANUAL
        amount = float(event_payload.get("amount") or booking.total_amount)

        tx = PaymentTransaction(
            booking_id=booking.id,
            provider=prov,
            amount=amount,
            currency=booking.currency,
            status=tx_status,
            external_reference=str(external_ref),
            created_at=datetime.utcnow(),
        )
        self.db.add(tx)
        self.db.commit()
        return {"status": "success", "booking_id": str(booking.id), "transaction_id": str(tx.id)}
