from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.payments.models import Payment, PaymentEvent


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **fields) -> Payment:
        payment = Payment(**fields)
        self.db.add(payment)
        self.db.flush()
        return payment

    def get(self, payment_id: UUID) -> Optional[Payment]:
        return self.db.get(Payment, payment_id)

    def get_by_order_id(self, order_id: str, *, lock: bool = False) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.order_id == order_id)
        if lock:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def has_succeeded_for_target(self, target_type: str, target_id: UUID) -> bool:
        stmt = (
            select(func.count())
            .select_from(Payment)
            .where(
                Payment.target_type == target_type,
                Payment.target_id == target_id,
                Payment.status == "succeeded",
            )
        )
        return self.db.execute(stmt).scalar_one() > 0

    def add_event(self, **fields) -> PaymentEvent:
        event = PaymentEvent(**fields)
        self.db.add(event)
        self.db.flush()
        return event

    def succeeded_totals(self) -> List[Tuple[str, Decimal, int]]:
        """Money actually received, per currency (never added across currencies)."""
        rows = self.db.execute(
            select(Payment.currency, func.coalesce(func.sum(Payment.amount), 0), func.count())
            .where(Payment.status == "succeeded")
            .group_by(Payment.currency)
            .order_by(Payment.currency)
        ).all()
        return [(currency, Decimal(str(total)), count) for currency, total, count in rows]

    def list_payments(
        self, status: Optional[str], page: int, page_size: int
    ) -> Tuple[List[Payment], int]:
        base = select(Payment)
        count = select(func.count()).select_from(Payment)
        if status:
            base = base.where(Payment.status == status)
            count = count.where(Payment.status == status)
        total = self.db.execute(count).scalar_one()
        rows = (
            self.db.execute(
                base.order_by(Payment.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total
