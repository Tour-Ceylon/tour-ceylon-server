from pydantic import BaseModel, Field


class AdminSettingsBase(BaseModel):
    siteName: str
    contactEmail: str
    defaultCurrency: str


class AdminSettingsUpdate(AdminSettingsBase):
    platformFeePercent: float | None = Field(None, ge=0, le=100)


class AdminSettingsResponse(AdminSettingsBase):
    platformFeePercent: float = 15

