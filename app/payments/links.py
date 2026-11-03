"""Signed, expiring links that let a guest pay for an approved stay request from an email."""
from datetime import datetime, timedelta, timezone
from typing import Tuple
from uuid import UUID

from jose import ExpiredSignatureError, JWTError, jwt

from app.config.settings import settings
from app.payments.errors import PaymentError

PURPOSE = "inquiry_payment"
ALGORITHM = "HS256"


def create_payment_token(inquiry_id: UUID) -> Tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.PAYMENT_LINK_TTL_HOURS)
    claims = {"sub": str(inquiry_id), "purpose": PURPOSE, "exp": expires_at}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM), expires_at


def read_payment_token(token: str) -> UUID:
    """Return the inquiry id a token was issued for, or raise PaymentError."""
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise PaymentError(410, "This payment link has expired. Please contact us and we will send a new one.")
    except JWTError:
        raise PaymentError(404, "This payment link is not valid.")
    if claims.get("purpose") != PURPOSE:
        raise PaymentError(404, "This payment link is not valid.")
    try:
        return UUID(str(claims.get("sub")))
    except ValueError:
        raise PaymentError(404, "This payment link is not valid.")


def payment_url(token: str) -> str:
    return f"{str(settings.CLIENT_APP_URL).rstrip('/')}/pay/{token}"
