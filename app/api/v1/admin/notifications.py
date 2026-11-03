"""FEAT-3: read-only view of the in-app notifications sent to customers."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.notification import ClientNotification, NotificationType

router = APIRouter(
    prefix="/notifications",
    tags=["admin-notifications"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))],
)


@router.get("")
def list_customer_notifications(
    type: NotificationType | None = Query(None),
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ClientNotification)
    if type:
        query = query.filter(ClientNotification.type == type)
    if unread_only:
        query = query.filter(ClientNotification.is_read.is_(False))
    total = query.count()
    rows = query.order_by(ClientNotification.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "message": n.message,
                "reference": n.reference,
                "recipient_email": n.recipient_email,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
