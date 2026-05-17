from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean
from app.models.base import Base, UUIDMixin, TimestampMixin


class TransportRoute(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transport_routes"

    pickup_place_name = Column(String, nullable=False)
    destination_place_name = Column(String, nullable=False)

    pickup_lat = Column(Numeric(10, 8), nullable=False)
    pickup_lng = Column(Numeric(11, 8), nullable=False)

    destination_lat = Column(Numeric(10, 8), nullable=False)
    destination_lng = Column(Numeric(11, 8), nullable=False)

    distance_km = Column(Numeric(10, 2), nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)

    route_polyline = Column(Text, nullable=True)
    is_popular_route = Column(Boolean, default=False)
