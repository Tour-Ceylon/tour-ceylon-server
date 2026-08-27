import math
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.driver import Driver, DriverLuggageCapacity, LuggageSizeType, VehicleModelPreset
from app.models.user import User
from app.schemas.driver_schema import DriverProfileUpdate, DriverSignupRequest


class DriverRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_luggage_size_types(self) -> List[LuggageSizeType]:
        return self.db.query(LuggageSizeType).order_by(LuggageSizeType.sort_order.asc()).all()

    def get_vehicle_model_presets(self, active_only: bool = True) -> List[VehicleModelPreset]:
        query = self.db.query(VehicleModelPreset)
        if active_only:
            query = query.filter(VehicleModelPreset.is_active.is_(True))
        return query.order_by(VehicleModelPreset.make.asc(), VehicleModelPreset.model.asc()).all()

    def get_preset_by_id(self, preset_id: UUID) -> Optional[VehicleModelPreset]:
        return self.db.query(VehicleModelPreset).filter(VehicleModelPreset.id == preset_id).first()

    def get_driver_by_id(self, driver_id: UUID) -> Optional[Driver]:
        return (
            self.db.query(Driver)
            .options(
                joinedload(Driver.user),
                joinedload(Driver.luggage_capacities).joinedload(DriverLuggageCapacity.luggage_size_type),
            )
            .filter(Driver.id == driver_id)
            .first()
        )

    def get_driver_by_user_id(self, user_id: UUID) -> Optional[Driver]:
        return (
            self.db.query(Driver)
            .options(
                joinedload(Driver.user),
                joinedload(Driver.luggage_capacities).joinedload(DriverLuggageCapacity.luggage_size_type),
            )
            .filter(Driver.user_id == user_id)
            .first()
        )

    def get_driver_by_nic(self, nic_number: str) -> Optional[Driver]:
        return self.db.query(Driver).filter(Driver.nic_number == nic_number).first()

    def get_driver_by_plate(self, plate_number: str) -> Optional[Driver]:
        return self.db.query(Driver).filter(Driver.vehicle_plate_number == plate_number).first()

    def create_driver(
        self,
        user: User,
        data: DriverSignupRequest,
    ) -> Driver:
        driver = Driver(
            user_id=user.id,
            nic_number=data.nic_number,
            license_number=data.license_number,
            license_photo_url=data.license_photo_url,
            nic_photo_url=data.nic_photo_url,
            vehicle_registration_doc_url=data.vehicle_registration_doc_url,
            insurance_doc_url=data.insurance_doc_url,
            police_clearance_doc_url=data.police_clearance_doc_url,
            vehicle_model_preset_id=data.vehicle_model_preset_id,
            vehicle_make=data.vehicle_make,
            vehicle_model=data.vehicle_model,
            vehicle_plate_number=data.vehicle_plate_number,
            seats=data.seats,
            status="pending_review",
            is_active=True,
        )
        self.db.add(driver)
        self.db.flush()

        for item in data.luggage_capacities:
            cap = DriverLuggageCapacity(
                driver_id=driver.id,
                luggage_size_type_id=item.luggage_size_type_id,
                quantity=item.quantity,
            )
            self.db.add(cap)

        self.db.commit()
        return self.get_driver_by_id(driver.id)

    def update_driver_profile(self, driver_id: UUID, data: DriverProfileUpdate) -> Optional[Driver]:
        driver = self.get_driver_by_id(driver_id)
        if not driver:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if hasattr(driver, key):
                setattr(driver, key, value)

        self.db.commit()
        self.db.refresh(driver)
        return driver

    def update_driver_status(self, driver_id: UUID, status: str) -> Optional[Driver]:
        driver = self.get_driver_by_id(driver_id)
        if not driver:
            return None

        driver.status = status
        self.db.commit()
        self.db.refresh(driver)
        return driver

    def list_drivers(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Driver], int]:
        query = self.db.query(Driver).join(User, Driver.user_id == User.id)

        if status:
            query = query.filter(Driver.status == status)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    Driver.nic_number.ilike(search_pattern),
                    Driver.vehicle_plate_number.ilike(search_pattern),
                    Driver.vehicle_make.ilike(search_pattern),
                    Driver.vehicle_model.ilike(search_pattern),
                )
            )

        total = query.count()
        drivers = (
            query.options(
                joinedload(Driver.user),
                joinedload(Driver.luggage_capacities).joinedload(DriverLuggageCapacity.luggage_size_type),
            )
            .order_by(Driver.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return drivers, total
