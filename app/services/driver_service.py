import math
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enum import UserRole
from app.models.user import User
from app.repositories.driver_repository import DriverRepository
from app.schemas.driver_schema import (
    DriverListResponse,
    DriverLuggageCapacityResponseItem,
    DriverProfileUpdate,
    DriverResponse,
    DriverSignupRequest,
    LuggageSizeTypeResponse,
    VehicleModelPresetResponse,
)


class DriverService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DriverRepository(db)

    def _to_driver_response(self, driver) -> DriverResponse:
        capacities = []
        if driver.luggage_capacities:
            for cap in driver.luggage_capacities:
                name = cap.luggage_size_type.name if cap.luggage_size_type else None
                capacities.append(
                    DriverLuggageCapacityResponseItem(
                        luggage_size_type_id=cap.luggage_size_type_id,
                        name=name,
                        quantity=cap.quantity,
                    )
                )

        phone = None
        if driver.user and driver.user.business_profile:
            phone = driver.user.business_profile.get("phone")

        return DriverResponse(
            id=driver.id,
            user_id=driver.user_id,
            full_name=driver.user.full_name if driver.user else None,
            email=driver.user.email if driver.user else None,
            phone=phone,
            nic_number=driver.nic_number,
            license_number=driver.license_number,
            license_photo_url=driver.license_photo_url,
            nic_photo_url=driver.nic_photo_url,
            vehicle_registration_doc_url=driver.vehicle_registration_doc_url,
            insurance_doc_url=driver.insurance_doc_url,
            police_clearance_doc_url=driver.police_clearance_doc_url,
            vehicle_model_preset_id=driver.vehicle_model_preset_id,
            vehicle_make=driver.vehicle_make,
            vehicle_model=driver.vehicle_model,
            vehicle_plate_number=driver.vehicle_plate_number,
            seats=driver.seats,
            status=driver.status,
            base_location=driver.base_location,
            languages_spoken=driver.languages_spoken or [],
            years_experience=driver.years_experience,
            bank_account_holder=driver.bank_account_holder,
            bank_name=driver.bank_name,
            bank_account_number=driver.bank_account_number,
            rating=float(driver.rating) if driver.rating is not None else None,
            is_active=driver.is_active,
            created_at=driver.created_at,
            updated_at=driver.updated_at,
            luggage_capacities=capacities,
        )

    def get_luggage_size_types(self) -> List[LuggageSizeTypeResponse]:
        items = self.repo.get_luggage_size_types()
        return [LuggageSizeTypeResponse.model_validate(item) for item in items]

    def get_vehicle_model_presets(self) -> List[VehicleModelPresetResponse]:
        items = self.repo.get_vehicle_model_presets()
        return [VehicleModelPresetResponse.model_validate(item) for item in items]

    def signup_driver(self, data: DriverSignupRequest) -> DriverResponse:
        # Check if email already exists
        existing_user = self.db.query(User).filter(User.email == data.email).first()
        if existing_user:
            if existing_user.role == UserRole.DRIVER:
                # If driver record already exists
                existing_driver = self.repo.get_driver_by_user_id(existing_user.id)
                if existing_driver:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="A driver with this email already exists.",
                    )
            user = existing_user
            user.role = UserRole.DRIVER
            user.full_name = data.full_name
            user.business_profile = {"phone": data.phone}
        else:
            clerk_id = data.clerk_user_id
            if not clerk_id:
                try:
                    from app.core.auth.clerk import create_clerk_user
                    clerk_id = create_clerk_user(
                        email=data.email,
                        password=data.password,
                        full_name=data.full_name,
                        role="DRIVER",
                        vendor_status="pending",
                        company_name=f"{data.vehicle_make} {data.vehicle_model}".strip() if data.vehicle_make else None,
                    )
                except Exception:
                    pass

            user = User(
                clerk_user_id=clerk_id,
                email=data.email,
                full_name=data.full_name,
                country=data.country or "Sri Lanka",
                role=UserRole.DRIVER,
                is_active=True,
                business_profile={"phone": data.phone},
            )
            self.db.add(user)
            self.db.flush()

        # Check NIC uniqueness
        if self.repo.get_driver_by_nic(data.nic_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A driver with this NIC number already exists.",
            )

        # Check Plate number uniqueness
        if self.repo.get_driver_by_plate(data.vehicle_plate_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A vehicle with this plate number is already registered.",
            )

        # Create driver profile
        driver = self.repo.create_driver(user=user, data=data)
        return self._to_driver_response(driver)

    def get_driver_by_user_id(self, user_id: UUID) -> DriverResponse:
        driver = self.repo.get_driver_by_user_id(user_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver profile not found.",
            )
        return self._to_driver_response(driver)

    def get_driver_by_id(self, driver_id: UUID) -> DriverResponse:
        driver = self.repo.get_driver_by_id(driver_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found.",
            )
        return self._to_driver_response(driver)

    def update_driver_profile(self, user_id: UUID, data: DriverProfileUpdate) -> DriverResponse:
        driver = self.repo.get_driver_by_user_id(user_id)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver profile not found.",
            )
        updated = self.repo.update_driver_profile(driver.id, data)
        return self._to_driver_response(updated)

    def update_driver_status(self, driver_id: UUID, status: str) -> DriverResponse:
        driver = self.repo.update_driver_status(driver_id, status)
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found.",
            )
        return self._to_driver_response(driver)

    def list_drivers(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> DriverListResponse:
        skip = (page - 1) * per_page
        drivers, total = self.repo.list_drivers(status=status, search=search, skip=skip, limit=per_page)
        return DriverListResponse(
            drivers=[self._to_driver_response(d) for d in drivers],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total > 0 else 0,
        )
