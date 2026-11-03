from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, and_
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import foreign, relationship

from app.models.base import Base
from app.models.enum import MediaOwnerType
from app.models.media import MediaAsset



class AdminSettings(Base):
    __tablename__ = "AdminSettings"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    site_name = Column(String, nullable=False, default="Tour Ceylon")
    contact_email = Column(String, nullable=False, default="support@tourceylon.com")
    default_currency = Column(String, nullable=False, default="LKR")
    # UI-11: the platform fee shown in booking details. Was hardcoded as 15% in the portal.
    platform_fee_percent = Column(Numeric(5, 2), nullable=False, default=15, server_default="15")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
