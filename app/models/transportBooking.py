from sqlalchemy import Column, String, Text, Integer, Numeric, Date, Time, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin


class TransportBooking(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transport_bookings"

    booking_reference = Column(String, unique=True, index=True, nullable=False)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    vehicle_category_id = Column(UUID(as_uuid=True), ForeignKey("vehicle_categories.id"), nullable=False, index=True)

    # Customer Details
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_country = Column(String, nullable=True)

    # Route Details
    pickup_location = Column(String, nullable=False)
    pickup_lat = Column(Numeric(10, 8), nullable=True)
    pickup_lng = Column(Numeric(11, 8), nullable=True)

    destination_location = Column(String, nullable=False)
    destination_lat = Column(Numeric(10, 8), nullable=True)
    destination_lng = Column(Numeric(11, 8), nullable=True)

    distance_km = Column(Numeric(10, 2), nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)

    # Travel Details
    travel_date = Column(Date, nullable=False)
    pickup_time = Column(Time, nullable=False)

    passengers_count = Column(Integer, nullable=False, default=1)
    luggage_count = Column(Integer, nullable=False, default=0)

    special_requests = Column(Text, nullable=True)

    # Pricing
    base_fare = Column(Numeric(10, 2), nullable=False)
    price_per_km = Column(Numeric(10, 2), nullable=False)
    
    route_price = Column(Numeric(10, 2), nullable=False)
    extra_charges = Column(Numeric(10, 2), nullable=False, default=0.0)
    
    total_price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False, default="USD")

    # Status
    # pending, confirmed, completed, cancelled
    booking_status = Column(String, nullable=False, default="pending")
    
    # unpaid, paid, refunded
    payment_status = Column(String, nullable=False, default="unpaid")

    # Admin
    internal_notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="transport_bookings")
    vehicle_category = relationship("VehicleCategory", back_populates="bookings")
