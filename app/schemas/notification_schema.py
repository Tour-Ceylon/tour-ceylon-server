from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.notification import NotificationType


class ClientNotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    reference: Optional[str] = None
    booking_inquiry_id: Optional[UUID] = Field(None, alias="bookingInquiryId")
    is_read: bool = Field(alias="isRead")
    created_at: datetime = Field(alias="createdAt")
    payload: Dict[str, Any] = {}

    class Config:
        from_attributes = True
        populate_by_name = True


class ClientNotificationListResponse(BaseModel):
    items: List[ClientNotificationResponse]
    unread_count: int = Field(alias="unreadCount")
    total: int

    class Config:
        from_attributes = True
        populate_by_name = True


class MarkNotificationReadRequest(BaseModel):
    notification_id: UUID


class BookingConfirmationCustomer(BaseModel):
    name: str
    email: str
    phone: str
    nationality: str


class BookingConfirmationItem(BaseModel):
    title: str
    listing_id: UUID = Field(alias="listingId")
    type: str
    travel_date: Optional[str] = Field(None, alias="travelDate")
    travelers: int
    price: float
    currency: str


class BookingConfirmationPreviewResponse(BaseModel):
    reference: str
    status: str
    customer: BookingConfirmationCustomer
    items: List[BookingConfirmationItem]
    subtotal: float
    total: float
    currency: str
    special_requests: Optional[str] = Field(None, alias="specialRequests")
    confirmed_at: Optional[datetime] = Field(None, alias="confirmedAt")
    updated_at: datetime = Field(alias="updatedAt")
    support: Dict[str, Any]
    next_steps: List[str] = Field(alias="nextSteps")
    important_notes: List[str] = Field(alias="importantNotes")

    class Config:
        populate_by_name = True


class CreateNotificationRequest(BaseModel):
    user_id: Optional[UUID] = None
    recipient_email: str
    type: NotificationType
    title: str
    message: str
    booking_inquiry_id: Optional[UUID] = None
    reference: Optional[str] = None
    payload: Dict[str, Any] = {}