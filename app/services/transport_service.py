import os
import random
import string
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.transportRoute import TransportRoute
from app.models.vehicleCategory import VehicleCategory
from app.models.transportBooking import TransportBooking
from app.integrations.geoapify import geoapify_routing_service
from app.integrations.google_maps import google_maps_service
from app.integrations.local_distance import estimate_distance_matrix
from app.schemas.transport_schema import (
    TransportEstimateRequest,
    TransportEstimateResponse,
    VehicleEstimate,
    TransportBookingCreate,
    TransportBookingResponse
)

class TransportService:
    def __init__(self, db: Session):
        self.db = db

    async def get_estimates(self, request: TransportEstimateRequest) -> TransportEstimateResponse:
        origin_coordinates = self._request_coordinates(
            request.pickup_lat,
            request.pickup_lng,
        )
        destination_coordinates = self._request_coordinates(
            request.destination_lat,
            request.destination_lng,
        )

        # 1. Get distance and duration from the cheapest hosted routing provider first.
        distance_info = None
        if origin_coordinates and destination_coordinates:
            distance_info = self._get_cached_route(
                request.pickup_location,
                request.destination_location,
                origin_coordinates,
                destination_coordinates,
            )

            if not distance_info:
                distance_info = await geoapify_routing_service.get_route_by_coordinates(
                    origin_coordinates,
                    destination_coordinates,
                )
                self._cache_route(
                    request.pickup_location,
                    request.destination_location,
                    origin_coordinates,
                    destination_coordinates,
                    distance_info,
                )

        if not distance_info:
            distance_info = await geoapify_routing_service.get_distance_matrix(
                request.pickup_location,
                request.destination_location
            )

        if not distance_info and os.getenv("GOOGLE_MAPS_FALLBACK", "").lower() == "true":
            distance_info = await google_maps_service.get_distance_matrix(
                request.pickup_location,
                request.destination_location
            )

        if not distance_info:
            distance_info = estimate_distance_matrix(
                request.pickup_location,
                request.destination_location
            )
        
        if not distance_info:
            raise ValueError("Could not calculate distance between locations")

        distance_km = distance_info["distance_km"]
        
        # 2. Fetch active vehicle categories
        categories = self.db.execute(
            select(VehicleCategory).filter(VehicleCategory.is_active == True).order_by(VehicleCategory.sort_order)
        ).scalars().all()

        estimates = []
        for cat in categories:
            # Pricing logic: base_fare + (distance * price_per_km)
            route_price = cat.base_fare + (Decimal(str(distance_km)) * cat.price_per_km)
            
            # Ensure minimum fare
            if route_price < cat.minimum_fare:
                route_price = cat.minimum_fare

            # TODO: Add logic for airport/night surcharges if applicable
            surcharges = Decimal("0.00")
            
            total_price = route_price + surcharges

            estimates.append(VehicleEstimate(
                category_id=cat.id,
                category_name=cat.name,
                image_url=cat.image_url,
                passenger_capacity=cat.passenger_capacity,
                luggage_capacity=cat.luggage_capacity,
                features=cat.features or [],
                base_fare=cat.base_fare,
                price_per_km=cat.price_per_km,
                route_price=route_price,
                surcharges=surcharges,
                total_price=total_price,
                currency=cat.currency
            ))

        return TransportEstimateResponse(
            pickup_location=request.pickup_location,
            destination_location=request.destination_location,
            distance_km=distance_km,
            duration_minutes=distance_info["duration_minutes"],
            estimates=estimates
        )

    async def search_locations(self, query: str):
        return await geoapify_routing_service.search_locations(query)

    def create_booking(self, booking_data: TransportBookingCreate, user_id: Optional[str] = None) -> TransportBooking:
        # Generate unique booking reference
        reference = self._generate_reference()
        
        db_booking = TransportBooking(
            booking_reference=reference,
            user_id=user_id,
            vehicle_category_id=booking_data.vehicle_category_id,
            
            customer_name=booking_data.customer_name,
            customer_email=booking_data.customer_email,
            customer_phone=booking_data.customer_phone,
            customer_country=booking_data.customer_country,
            
            pickup_location=booking_data.pickup_location,
            pickup_lat=booking_data.pickup_lat,
            pickup_lng=booking_data.pickup_lng,
            
            destination_location=booking_data.destination_location,
            destination_lat=booking_data.destination_lat,
            destination_lng=booking_data.destination_lng,
            
            distance_km=booking_data.distance_km,
            estimated_duration_minutes=booking_data.estimated_duration_minutes,
            
            travel_date=booking_data.travel_date,
            pickup_time=booking_data.pickup_time,
            
            passengers_count=booking_data.passengers_count,
            luggage_count=booking_data.luggage_count,
            special_requests=booking_data.special_requests,
            
            base_fare=booking_data.base_fare,
            price_per_km=booking_data.price_per_km,
            route_price=booking_data.route_price,
            extra_charges=booking_data.extra_charges,
            total_price=booking_data.total_price,
            currency=booking_data.currency,
            
            booking_status="pending",
            payment_status="unpaid"
        )
        
        self.db.add(db_booking)
        self.db.commit()
        self.db.refresh(db_booking)
        
        return db_booking

    def _generate_reference(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d")
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"TR-{timestamp}-{random_str}"

    def _request_coordinates(
        self,
        lat: Optional[Decimal],
        lng: Optional[Decimal],
    ) -> Optional[tuple[float, float]]:
        if lat is None or lng is None:
            return None
        return float(lat), float(lng)

    def _get_cached_route(
        self,
        pickup_name: str,
        destination_name: str,
        pickup: tuple[float, float],
        destination: tuple[float, float],
    ) -> Optional[dict]:
        try:
            route = self.db.execute(
                select(TransportRoute)
                .filter(
                    TransportRoute.pickup_place_name == pickup_name,
                    TransportRoute.destination_place_name == destination_name,
                    TransportRoute.pickup_lat == Decimal(str(round(pickup[0], 6))),
                    TransportRoute.pickup_lng == Decimal(str(round(pickup[1], 6))),
                    TransportRoute.destination_lat == Decimal(str(round(destination[0], 6))),
                    TransportRoute.destination_lng == Decimal(str(round(destination[1], 6))),
                )
                .order_by(TransportRoute.updated_at.desc())
            ).scalars().first()
        except SQLAlchemyError:
            self.db.rollback()
            return None

        if not route or route.distance_km is None or route.estimated_duration_minutes is None:
            return None

        return {
            "distance_km": float(route.distance_km),
            "distance_text": f"{float(route.distance_km):.1f} km",
            "duration_minutes": route.estimated_duration_minutes,
            "duration_text": f"{route.estimated_duration_minutes} mins",
        }

    def _cache_route(
        self,
        pickup_name: str,
        destination_name: str,
        pickup: tuple[float, float],
        destination: tuple[float, float],
        distance_info: Optional[dict],
    ) -> None:
        if not distance_info:
            return

        try:
            route = TransportRoute(
                pickup_place_name=pickup_name,
                destination_place_name=destination_name,
                pickup_lat=Decimal(str(round(pickup[0], 6))),
                pickup_lng=Decimal(str(round(pickup[1], 6))),
                destination_lat=Decimal(str(round(destination[0], 6))),
                destination_lng=Decimal(str(round(destination[1], 6))),
                distance_km=Decimal(str(round(float(distance_info["distance_km"]), 2))),
                estimated_duration_minutes=int(distance_info["duration_minutes"]),
                is_popular_route=False,
            )
            self.db.add(route)
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()

    # --- Category Management (Admin) ---

    def list_all_categories(self) -> List[VehicleCategory]:
        return self.db.execute(
            select(VehicleCategory).order_by(VehicleCategory.sort_order)
        ).scalars().all()

    def create_category(self, data: dict) -> VehicleCategory:
        db_cat = VehicleCategory(**data)
        self.db.add(db_cat)
        self.db.commit()
        self.db.refresh(db_cat)
        return db_cat

    def get_category(self, category_id: UUID) -> Optional[VehicleCategory]:
        return self.db.get(VehicleCategory, category_id)

    def update_category(self, category_id: UUID, data: dict) -> Optional[VehicleCategory]:
        db_cat = self.get_category(category_id)
        if not db_cat:
            return None
        
        for key, value in data.items():
            setattr(db_cat, key, value)
        
        self.db.commit()
        self.db.refresh(db_cat)
        return db_cat

    def delete_category(self, category_id: UUID) -> bool:
        db_cat = self.get_category(category_id)
        if not db_cat:
            return False
        
        # Soft delete by deactivating
        db_cat.is_active = False
        self.db.commit()
        return True

    # --- Booking Management (Admin) ---

    def list_all_bookings(self) -> List[TransportBooking]:
        return self.db.execute(
            select(TransportBooking).order_by(TransportBooking.created_at.desc())
        ).scalars().all()

    def get_booking_by_id(self, booking_id: UUID) -> Optional[TransportBooking]:
        return self.db.get(TransportBooking, booking_id)

    def update_booking_status(self, booking_id: UUID, status: str) -> Optional[TransportBooking]:
        db_booking = self.get_booking_by_id(booking_id)
        if not db_booking:
            return None
        
        db_booking.booking_status = status
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking

    def update_booking_notes(self, booking_id: UUID, notes: str) -> Optional[TransportBooking]:
        db_booking = self.get_booking_by_id(booking_id)
        if not db_booking:
            return None
        
        db_booking.internal_notes = notes
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking

    # --- Public API methods ---

    def list_active_categories(self) -> List[VehicleCategory]:
        return self.db.execute(
            select(VehicleCategory).filter(VehicleCategory.is_active == True).order_by(VehicleCategory.sort_order)
        ).scalars().all()

    def get_booking_by_reference(self, reference: str) -> Optional[TransportBooking]:
        return self.db.execute(
            select(TransportBooking).filter(TransportBooking.booking_reference == reference)
        ).scalar_one_or_none()


