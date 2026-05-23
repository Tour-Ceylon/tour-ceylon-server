from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, Field, computed_field

from app.models.enum import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields"""
    clerk_user_id: Optional[str] = None
    email: EmailStr
    full_name: Optional[str] = None
    country: Optional[str] = None
    role: UserRole = UserRole.TOURIST
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user"""
    vendor_status: Optional[str] = None
    approved_categories: Optional[List[str]] = None
    company_name: Optional[str] = None
    business_profile: Optional[Dict[str, Any]] = None



class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    country: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    # Vendor fields — only set by admin or internal sync
    vendor_status: Optional[str] = None
    approved_categories: Optional[List[str]] = None
    company_name: Optional[str] = None
    business_profile: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    """Schema for user API responses — includes vendor fields when present"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    # Vendor-specific fields (null for non-vendor users)
    vendor_status: Optional[str] = None
    approved_categories: Optional[List[str]] = None
    company_name: Optional[str] = None
    business_profile: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @computed_field
    @property
    def clerkUserId(self) -> Optional[str]:
        return self.clerk_user_id

    @computed_field
    @property
    def name(self) -> Optional[str]:
        return self.full_name

    @computed_field
    @property
    def vendorStatus(self) -> Optional[str]:
        return self.vendor_status

    @computed_field
    @property
    def approvedCategories(self) -> Optional[List[str]]:
        return self.approved_categories

    @computed_field
    @property
    def company(self) -> Optional[str]:
        return self.company_name

    @computed_field
    @property
    def businessProfile(self) -> Optional[Dict[str, Any]]:
        return self.business_profile


class UserInDB(UserResponse):
    """Schema for user stored in database (includes all fields)"""
    pass


class UserListResponse(BaseModel):
    """Schema for paginated user list responses"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserSearchParams(BaseModel):
    """Schema for user search parameters"""
    email: Optional[str] = None
    role: Optional[UserRole] = None
    country: Optional[str] = None
    is_active: Optional[bool] = None
    page: int = 1
    per_page: int = 20


class VendorApply(BaseModel):
    """Schema for submitting a vendor application"""
    business_name: str = Field(..., alias="businessName")
    vendor_name: str = Field(..., alias="vendorName")
    email: EmailStr
    phone: str
    country: str
    business_description: str = Field(..., alias="businessDescription")
    categories: List[str]

    model_config = ConfigDict(
        populate_by_name=True,
    )

