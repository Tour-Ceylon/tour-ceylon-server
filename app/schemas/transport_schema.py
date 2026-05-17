from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import date, time
from decimal import Decimal
from uuid import UUID

# Vehicle Category Schema
class VehicleCategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    passenger_capacity: int
    luggage_capacity: int
    base_fare: Decimal
    price_per_km: Decimal
    minimum_fare: Decimal
    airport_surcharge: Decimal
    night_surcharge: Decimal
    currency: str
    image_url: Optional[str] = None
    features: Optional[List[str]] = []

class VehicleCategoryCreate(VehicleCategoryBase):
    pass

class VehicleCategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    passenger_capacity: Optional[int] = None
    luggage_capacity: Optional[int] = None
    base_fare: Optional[Decimal] = None
    price_per_km: Optional[Decimal] = None
    minimum_fare: Optional[Decimal] = None
    airport_surcharge: Optional[Decimal] = None
    night_surcharge: Optional[Decimal] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    features: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class VehicleCategoryResponse(VehicleCategoryBase):
    id: UUID

    class Config:
        from_attributes = True

# Estimation schemas
class TransportEstimateRequest(BaseModel):
    pickup_location: str  # Can be lat,lng or name
    destination_location: str
    travel_date: date
    pickup_time: time

class VehicleEstimate(BaseModel):
    category_id: UUID
    category_name: str
    image_url: Optional[str] = None
    passenger_capacity: int
    luggage_capacity: int
    features: List[str]
    
    base_fare: Decimal
    price_per_km: Decimal
    route_price: Decimal
    surcharges: Decimal
    total_price: Decimal
    currency: str

class TransportEstimateResponse(BaseModel):
    pickup_location: str
    destination_location: str
    distance_km: float
    duration_minutes: int
    estimates: List[VehicleEstimate]

# Booking schemas
class TransportBookingCreate(BaseModel):
    vehicle_category_id: UUID
    
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
    distance_km: Decimal
    estimated_duration_minutes: int

    # Travel Details
    travel_date: date
    pickup_time: time
    passengers_count: int
    luggage_count: int
    special_requests: Optional[str] = None

    # Pricing (Sent from frontend based on estimate)
    base_fare: Decimal
    price_per_km: Decimal
    route_price: Decimal
    extra_charges: Decimal
    total_price: Decimal
    currency: str

class TransportBookingResponse(BaseModel):
    id: UUID
    booking_reference: str
    booking_status: str
    payment_status: str

    class Config:
        from_attributes = True

class TransportBookingDetailResponse(BaseModel):
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
    distance_km: Decimal
    estimated_duration_minutes: int

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

    # Status
    booking_status: str
    payment_status: str
    
    # Admin
    internal_notes: Optional[str] = None
    
    vehicle_category: Optional[VehicleCategoryResponse] = None

    class Config:
        from_attributes = True

class TransportBookingStatusUpdate(BaseModel):
    booking_status: str # pending, confirmed, completed, cancelled

class TransportBookingNotesUpdate(BaseModel):
    internal_notes: str
