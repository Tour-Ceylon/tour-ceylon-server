from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.transport_schema import VehicleCategoryResponse


class AdminAssignDriverRequest(BaseModel):
    driver_id: UUID = Field(..., description="UUID of the approved driver to assign")


class AdminAssignedDriverInfo(BaseModel):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    nic_number: str
    vehicle_make: str
    vehicle_model: str
    vehicle_plate_number: str
    seats: int
    status: str
    is_online: bool = False
    rating: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class AdminTransportBookingDetailResponse(BaseModel):
    id: UUID
    booking_reference: str

    # Customer Details
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    customer_country: Optional[str] = None

    # Route Details
    pickup_location: str
    pickup_lat: Optional[Decimal] = None
    pickup_lng: Optional[Decimal] = None
    destination_location: str
    destination_lat: Optional[Decimal] = None
    destination_lng: Optional[Decimal] = None
    distance_km: Optional[Decimal] = None
    estimated_duration_minutes: Optional[int] = None

    # Travel Details
    travel_date: date
    pickup_time: time
    passengers_count: int
    luggage_count: int
    special_requests: Optional[str] = None

    # Pricing
    base_fare: Decimal
    price_per_km: Decimal
    route_price: Decimal
    extra_charges: Decimal
    total_price: Decimal
    currency: str

    # Statuses
    booking_status: str
    payment_status: str
    assignment_status: str
    assigned_at: Optional[datetime] = None
    driver_responded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # Admin
    internal_notes: Optional[str] = None

    # Linked Objects
    vehicle_category: Optional[VehicleCategoryResponse] = None
    driver: Optional[AdminAssignedDriverInfo] = None

    model_config = ConfigDict(from_attributes=True)


class AdminTransportBookingListResponse(BaseModel):
    bookings: List[AdminTransportBookingDetailResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    unassigned_count: int = 0
    assigned_count: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
