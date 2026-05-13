from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class VendorBase(BaseModel):
    name: str
    email: str
    phone: str | None = None
    description: str | None = None
    contact_person: str | None = None
    address: str | None = None
    is_active: bool = True


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    description: str | None = None
    contact_person: str | None = None
    address: str | None = None
    is_active: bool | None = None


class VendorResponse(VendorBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VendorListResponse(BaseModel):
    items: list[VendorResponse]
    total: int
