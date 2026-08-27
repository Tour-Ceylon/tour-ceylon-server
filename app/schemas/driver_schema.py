from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.enum import DriverStatus


class LuggageSizeTypeResponse(BaseModel):
    id: UUID
    name: str
    dimensions_display: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class VehicleModelPresetResponse(BaseModel):
    id: UUID
    make: str
    model: str
    vehicle_category_id: Optional[UUID] = None
    default_seats: int
    default_luggage_capacity: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DriverLuggageCapacityItem(BaseModel):
    luggage_size_type_id: UUID
    quantity: int = Field(ge=0, default=0)


class DriverLuggageCapacityResponseItem(BaseModel):
    luggage_size_type_id: UUID
    name: Optional[str] = None
    quantity: int = 0

    model_config = ConfigDict(from_attributes=True)


class DriverSignupRequest(BaseModel):
    full_name: str
    nic_number: str
    email: EmailStr
    phone: str
    password: Optional[str] = None
    clerk_user_id: Optional[str] = None
    country: Optional[str] = "Sri Lanka"

    # Vehicle Information
    vehicle_model_preset_id: Optional[UUID] = None
    vehicle_make: str
    vehicle_model: str
    vehicle_plate_number: str
    seats: int = Field(ge=1, default=4)
    luggage_capacities: List[DriverLuggageCapacityItem] = Field(default_factory=list)

    # Documents
    license_number: Optional[str] = None
    license_photo_url: Optional[str] = None
    nic_photo_url: Optional[str] = None
    vehicle_registration_doc_url: Optional[str] = None
    insurance_doc_url: Optional[str] = None
    police_clearance_doc_url: Optional[str] = None


class DriverResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nic_number: str
    license_number: Optional[str] = None
    license_photo_url: Optional[str] = None
    nic_photo_url: Optional[str] = None
    vehicle_registration_doc_url: Optional[str] = None
    insurance_doc_url: Optional[str] = None
    police_clearance_doc_url: Optional[str] = None
    vehicle_model_preset_id: Optional[UUID] = None
    vehicle_make: str
    vehicle_model: str
    vehicle_plate_number: str
    seats: int
    status: str
    base_location: Optional[str] = None
    languages_spoken: Optional[List[str]] = Field(default_factory=list)
    years_experience: Optional[int] = None
    bank_account_holder: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    rating: Optional[float] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    luggage_capacities: List[DriverLuggageCapacityResponseItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DriverProfileUpdate(BaseModel):
    base_location: Optional[str] = None
    languages_spoken: Optional[List[str]] = None
    years_experience: Optional[int] = None
    bank_account_holder: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None


class DriverStatusUpdate(BaseModel):
    status: DriverStatus
    rejection_reason: Optional[str] = None


class DriverListResponse(BaseModel):
    drivers: List[DriverResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
