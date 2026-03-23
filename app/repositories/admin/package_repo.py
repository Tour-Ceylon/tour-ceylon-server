from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin_dashboard import Package


class AdminPackageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, package_data: dict) -> Package:
        package = Package(**package_data)
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def get_all(self) -> list[Package]:
        return self.db.query(Package).order_by(Package.created_at.desc()).all()

    def get_all_active(self) -> list[Package]:
        return (
            self.db.query(Package)
            .filter(Package.is_active.is_(True))
            .order_by(Package.created_at.desc())
            .all()
        )

    def get(self, package_id: UUID) -> Package | None:
        return self.db.query(Package).filter(Package.id == package_id).first()

    def get_active(self, package_id: UUID) -> Package | None:
        return (
            self.db.query(Package)
            .filter(Package.id == package_id, Package.is_active.is_(True))
            .first()
        )

    def update(self, package: Package, updates: dict) -> Package:
        for field, value in updates.items():
            setattr(package, field, value)
        self.db.commit()
        self.db.refresh(package)
        return package

    def delete(self, package_id: UUID) -> bool:
        package = self.get(package_id)
        if not package:
            return False
        self.db.delete(package)
        self.db.commit()
        return True

    def delete_all(self) -> None:
        self.db.query(Package).delete()
        self.db.commit()

