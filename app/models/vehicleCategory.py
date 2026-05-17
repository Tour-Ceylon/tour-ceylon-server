from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class VehicleCategory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vehicle_categories"

    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    passenger_capacity = Column(Integer, nullable=False)
    luggage_capacity = Column(Integer, nullable=False)

    base_fare = Column(Numeric(10, 2), nullable=False)
    price_per_km = Column(Numeric(10, 2), nullable=False)
    minimum_fare = Column(Numeric(10, 2), nullable=False)

    airport_surcharge = Column(Numeric(10, 2), nullable=True, default=0.0)
    night_surcharge = Column(Numeric(10, 2), nullable=True, default=0.0)

    currency = Column(String, nullable=False, default="USD")
    image_url = Column(Text, nullable=True)

    features = Column(JSON, nullable=True)  # Store list of features as JSON

    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # Relationships
    bookings = relationship("TransportBooking", back_populates="vehicle_category")
