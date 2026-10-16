from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
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


class DriverProfileChangeSubmit(BaseModel):
    """What a driver may propose. Anything else (status, rating, documents, vehicle...) is rejected."""

    model_config = ConfigDict(extra="forbid")

    base_location: Optional[str] = Field(None, min_length=2, max_length=255)
    languages_spoken: Optional[List[str]] = Field(None, max_length=10)
    years_experience: Optional[int] = Field(None, ge=0, le=60)
    bank_account_holder: Optional[str] = Field(None, min_length=2, max_length=150)
    bank_name: Optional[str] = Field(None, min_length=2, max_length=150)
    bank_account_number: Optional[str] = Field(None, max_length=40)

    @field_validator("base_location", "bank_account_holder", "bank_name", mode="before")
    @classmethod
    def _strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("languages_spoken", mode="before")
    @classmethod
    def _clean_languages(cls, value):
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("languages_spoken must be a list")
        cleaned: List[str] = []
        for item in value:
            text = str(item).strip()
            if not (2 <= len(text) <= 40):
                raise ValueError("Each language must be between 2 and 40 characters")
            if text.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(text)
        return cleaned

    @field_validator("bank_account_number", mode="before")
    @classmethod
    def _clean_account_number(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        if not re.fullmatch(r"[A-Za-z0-9 \-]+", text):
            raise ValueError("The account number can contain only letters, digits, spaces and hyphens")
        compact = re.sub(r"[ \-]", "", text).upper()
        if not (6 <= len(compact) <= 34):
            raise ValueError("The account number must be between 6 and 34 characters")
        return compact


class DriverProfileChangeResponse(BaseModel):
    id: UUID
    driver_id: UUID
    status: str  # pending | approved | rejected | withdrawn
    proposed: Dict[str, Any] = Field(default_factory=dict)
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DriverAvatarSubmissionResponse(BaseModel):
    id: UUID
    driver_id: UUID
    image_url: str
    status: str  # pending | approved | rejected | withdrawn
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DriverProfileChangeReject(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


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
    is_online: bool = False
    last_online_at: Optional[datetime] = None
    base_location: Optional[str] = None
    languages_spoken: Optional[List[str]] = Field(default_factory=list)
    years_experience: Optional[int] = None
    bank_account_holder: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    rating: Optional[float] = None
    is_active: bool
    total_earnings: float = 0.0
    completed_trips_count: int = 0
    active_trips_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    luggage_capacities: List[DriverLuggageCapacityResponseItem] = Field(default_factory=list)
    # Newest profile update the driver sent for review (any status); None if they never sent one.
    latest_profile_change: Optional[DriverProfileChangeResponse] = None
    # The approved photo to display, and the newest photo submission (any status) for review/status.
    avatar_url: Optional[str] = None
    latest_avatar_submission: Optional[DriverAvatarSubmissionResponse] = None

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
