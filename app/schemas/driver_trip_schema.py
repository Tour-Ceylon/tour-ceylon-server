from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# --- Availability ---

class DriverAvailabilityUpdate(BaseModel):
    is_online: bool


class DriverAvailabilityResponse(BaseModel):
    is_online: bool
    last_online_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Decline & Status Updates ---

class DriverTripDeclineRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for declining the trip assignment")
    note: Optional[str] = Field(None, description="Optional additional explanation")


class DriverTripStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status: en_route, arrived, in_progress, or completed")


# --- Trip Responses ---

class DriverTripVehicleInfo(BaseModel):
    category_name: Optional[str] = None
    passenger_capacity: Optional[int] = None
    luggage_capacity: Optional[int] = None


class DriverTripCustomerInfo(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    country: Optional[str] = None


class DriverTripSummaryResponse(BaseModel):
    id: UUID
    booking_reference: str
    travel_date: date
    pickup_time: time
    pickup_location: str
    destination_location: str
    distance_km: Optional[Decimal] = None
    estimated_duration_minutes: Optional[int] = None
    passengers_count: int
    luggage_count: int
    special_requests: Optional[str] = None
    total_price: Decimal
    currency: str
    booking_status: str
    payment_status: str
    assignment_status: str
    assigned_at: Optional[datetime] = None
    driver_responded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    customer_name: str
    customer_phone: str

    class Config:
        from_attributes = True


class DriverTripDetailResponse(BaseModel):
    id: UUID
    booking_reference: str
    travel_date: date
    pickup_time: time
    pickup_location: str
    pickup_lat: Optional[Decimal] = None
    pickup_lng: Optional[Decimal] = None
    destination_location: str
    destination_lat: Optional[Decimal] = None
    destination_lng: Optional[Decimal] = None
    distance_km: Optional[Decimal] = None
    estimated_duration_minutes: Optional[int] = None
    passengers_count: int
    luggage_count: int
    special_requests: Optional[str] = None
    base_fare: Decimal
    price_per_km: Decimal
    route_price: Decimal
    extra_charges: Decimal
    total_price: Decimal
    currency: str
    booking_status: str
    payment_status: str
    assignment_status: str
    assigned_at: Optional[datetime] = None
    driver_responded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    customer: DriverTripCustomerInfo
    vehicle_category_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- Decline History ---

class DriverTripDeclineRecordResponse(BaseModel):
    id: UUID
    transport_booking_id: UUID
    booking_reference: Optional[str] = None
    pickup_location: Optional[str] = None
    destination_location: Optional[str] = None
    travel_date: Optional[date] = None
    total_price: Optional[Decimal] = None
    currency: Optional[str] = None
    reason: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Earnings ---

class DriverDailyEarningItem(BaseModel):
    date: str
    day_name: str
    earnings: Decimal
    trip_count: int


class DriverEarningsResponse(BaseModel):
    period: str  # today, week, month
    total_earnings: Decimal
    trip_count: int
    currency: str = "USD"
    daily_breakdown: List[DriverDailyEarningItem] = []
    start_date: date
    end_date: date
