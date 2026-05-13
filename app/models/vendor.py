from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class Vendor(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "vendors"

    # Basic Information
    name = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Contact Information
    contact_person = Column(String, nullable=True)
    address = Column(Text, nullable=True)

    # Relationships
    packages = relationship("Package", back_populates="vendor")
    listings = relationship("Listing", back_populates="vendor")
