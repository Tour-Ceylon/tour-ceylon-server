from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CheckoutBody(BaseModel):
    target_type: Literal["transport_booking", "booking_inquiry"]
    target_id: UUID
    # Guests prove ownership with the reference and email they booked with.
    booking_reference: Optional[str] = None
    customer_email: Optional[str] = None
    # What the customer was shown; the server rejects the checkout if its own price differs.
    expected_amount: Optional[Decimal] = None


class CheckoutResponse(BaseModel):
    payment_id: UUID
    order_id: str
    url: str
    method: str
    fields: Dict[str, str]
    amount: Decimal
    currency: str


class PaymentStatusResponse(BaseModel):
    payment_id: UUID
    order_id: str
    status: str
    amount: Decimal
    currency: str


class AdminPaymentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target_type: str
    target_id: UUID
    provider: str
    order_id: str
    amount: Decimal
    currency: str
    status: str
    provider_payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AdminPaymentList(BaseModel):
    items: List[AdminPaymentItem]
    total: int
    page: int
    page_size: int
