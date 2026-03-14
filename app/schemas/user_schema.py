from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.enum import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr
    full_name: Optional[str] = None
    country: Optional[str] = None
    role: UserRole = UserRole.TOURIST
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user"""
    pass


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    country: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user API responses"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    """Schema for user stored in database (includes all fields)"""
    pass


class UserListResponse(BaseModel):
    """Schema for paginated user list responses"""
    users: list[UserResponse]
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