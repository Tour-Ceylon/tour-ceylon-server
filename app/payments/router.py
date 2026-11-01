import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import _decode_and_verify_clerk_token, _resolve_local_user, bearer_scheme
from app.config.database import get_db
from app.core.rate_limit import enforce_payment_notify_rate_limit
from app.integrations.email_provider import email_provider
from app.models.user import User
from app.payments import service
from app.payments.base import PaymentProviderError
from app.payments.registry import get_provider
from app.payments.repository import PaymentRepository
from app.payments.schemas import CheckoutBody, CheckoutResponse, PaymentStatusResponse

logger = logging.getLogger("app.payments")

router = APIRouter()


def get_optional_user(
    credentials=Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Signed-in user if a valid Clerk token is sent, otherwise None (guest)."""
    if not credentials:
        return None
    try:
        claims = _decode_and_verify_clerk_token(credentials.credentials)
        return _resolve_local_user(db=db, claims=claims)
    except HTTPException:
        return None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    body: CheckoutBody,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    try:
        payment, instructions = service.initiate_checkout(
            db,
            target_type=body.target_type,
            target_id=body.target_id,
            user=user,
            booking_reference=body.booking_reference,
            customer_email=body.customer_email,
        )
    except service.PaymentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return CheckoutResponse(
        payment_id=payment.id,
        order_id=payment.order_id,
        url=instructions.url,
        method=instructions.method,
        fields=instructions.fields,
    )


def _send_payment_received_task(notice) -> None:
    try:
        email_provider.send_transport_payment_received(notice)
    except Exception:  # an email problem must never affect the webhook
        logger.exception("Payment received email failed for %s", notice.booking_reference)


@router.post("/payhere/notify", response_class=PlainTextResponse)
async def payhere_notify(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Public webhook called by PayHere; authenticated only by its md5sig."""
    enforce_payment_notify_rate_limit(_client_ip(request))
    raw_body = await request.body()
    try:
        provider = get_provider()
        if provider.name != "payhere":
            raise PaymentProviderError("PayHere is not the active payment provider")
    except PaymentProviderError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Payments disabled")

    result = service.handle_notification(db, raw_body, dict(request.headers))
    if result.paid_notice is not None:
        background_tasks.add_task(_send_payment_received_task, result.paid_notice)
    return PlainTextResponse(result.message, status_code=result.http_status)


@router.get("/{payment_id}/status", response_model=PaymentStatusResponse)
def get_payment_status(
    payment_id: UUID,
    email: Optional[str] = Query(default=None, description="Customer email, for guest bookings"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    payment = PaymentRepository(db).get(payment_id)
    if payment is None or not service.can_view_payment(payment, db, user, email):
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentStatusResponse(
        payment_id=payment.id,
        order_id=payment.order_id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
    )
