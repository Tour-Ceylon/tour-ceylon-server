from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.config.database import Base


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, default=1)
    site_name = Column(String, nullable=False, default="Tour Ceylon")
    contact_email = Column(String, nullable=False, default="support@tourceylon.com")
    default_currency = Column(String, nullable=False, default="USD")
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
