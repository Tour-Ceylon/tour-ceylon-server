from typing import Optional, Dict, Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role, get_current_user
from app.models.user import User
from app.models.enum import UserRole
from app.services.payment_service import PaymentService

router = APIRouter()


class RefundRequest(BaseModel):
    booking_id: UUID
    amount: Optional[float] = None
    reason: Optional[str] = None


class TransactionResponse(BaseModel):
    id: UUID
    booking_id: UUID
    provider: str
    amount: float
    currency: str
    status: str
    external_reference: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/webhook/{provider}")
async def handle_payment_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """
    Gateway webhook receiver with idempotency protection and signature support (SRV-PAY-02).
    """
    payload = await request.json()
    service = PaymentService(db)
    return service.handle_webhook_event(provider, payload, signature=x_signature)


@router.post("/refund")
def process_booking_refund(
    refund_data: RefundRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Admin-only endpoint to process booking refunds and record immutable ledger rows (SRV-PAY-02).
    """
    service = PaymentService(db)
    tx = service.process_refund(
        booking_id=refund_data.booking_id,
        amount=refund_data.amount,
        reason=refund_data.reason,
        admin_user_id=current_user.id,
    )
    return {
        "status": "refunded",
        "booking_id": refund_data.booking_id,
        "transaction_id": tx.id,
        "amount": tx.amount,
    }


@router.get("/transactions/{booking_id}", response_model=List[TransactionResponse])
def get_booking_transactions(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    View immutable payment transaction history for a booking (Admin, Vendor, or Booking Tourist).
    """
    service = PaymentService(db)
    return service.get_booking_transactions(booking_id)
