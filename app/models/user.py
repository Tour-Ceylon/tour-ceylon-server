from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, Text, Enum, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base
from app.models.enum import UserRole

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    country = Column(String)
    role = Column(
        Enum(UserRole),
        default=UserRole.TOURIST,
        nullable=False
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )




