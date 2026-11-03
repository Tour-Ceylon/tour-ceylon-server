from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.config.database import get_db
from app.models.enum import UserRole
from app.payments.repository import PaymentRepository
from app.payments.schemas import AdminPaymentCurrencyTotal, AdminPaymentItem, AdminPaymentList, AdminPaymentSummary

router = APIRouter(
    prefix="/payments",
    tags=["admin-payments"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))],
)


@router.get("", response_model=AdminPaymentList)
def list_payments(
    status: Optional[str] = Query(None, description="initiated, pending, succeeded, failed, cancelled, chargedback"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows, total = PaymentRepository(db).list_payments(status, page, page_size)
    return AdminPaymentList(
        items=[AdminPaymentItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=AdminPaymentSummary)
def payments_summary(db: Session = Depends(get_db)):
    """FEAT-4: money received so far, per currency."""
    return AdminPaymentSummary(
        received=[
            AdminPaymentCurrencyTotal(currency=currency, total=total, count=count)
            for currency, total, count in PaymentRepository(db).succeeded_totals()
        ]
    )
