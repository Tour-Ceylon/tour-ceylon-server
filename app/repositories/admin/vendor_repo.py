from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.vendor import Vendor
from app.models.admin_dashboard import Package


class AdminVendorRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> Vendor:
        """Create a new vendor"""
        vendor = Vendor(**kwargs)
        self.db.add(vendor)
        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    def get(self, vendor_id: UUID) -> Vendor | None:
        """Get vendor by ID"""
        return self.db.query(Vendor).filter(Vendor.id == vendor_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Vendor]:
        """Get all vendors"""
        return self.db.query(Vendor).offset(skip).limit(limit).all()

    def get_all_active(self) -> list[Vendor]:
        """Get all active vendors"""
        return self.db.query(Vendor).filter(Vendor.is_active == True).all()

    def get_count(self) -> int:
        """Get total vendor count"""
        return self.db.query(func.count(Vendor.id)).scalar() or 0

    def update(self, vendor: Vendor, updates: dict) -> Vendor:
        """Update a vendor"""
        for key, value in updates.items():
            if hasattr(vendor, key) and value is not None:
                setattr(vendor, key, value)
        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    def delete(self, vendor_id: UUID) -> bool:
        """Delete a vendor (soft delete via is_active)"""
        vendor = self.get(vendor_id)
        if vendor is None:
            return False
        vendor.is_active = False
        self.db.commit()
        return True

    def search(self, query: str, skip: int = 0, limit: int = 100) -> list[Vendor]:
        """Search vendors by name or email"""
        return (
            self.db.query(Vendor)
            .filter(
                (Vendor.name.ilike(f"%{query}%")) | (Vendor.email.ilike(f"%{query}%"))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
