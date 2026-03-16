from pydantic import BaseModel


class AdminSettingsBase(BaseModel):
    siteName: str
    contactEmail: str
    defaultCurrency: str


class AdminSettingsUpdate(AdminSettingsBase):
    pass


class AdminSettingsResponse(AdminSettingsBase):
    pass

