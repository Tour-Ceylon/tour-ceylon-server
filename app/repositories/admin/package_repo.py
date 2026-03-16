from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin_dashboard import AdminPackage


class AdminPackageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, package_data: dict) -> AdminPackage:
        package = AdminPackage(**package_data)
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def get_all(self) -> list[AdminPackage]:
        return self.db.query(AdminPackage).order_by(AdminPackage.created_at.desc()).all()

    def get(self, package_id: UUID) -> AdminPackage | None:
        return self.db.query(AdminPackage).filter(AdminPackage.id == package_id).first()

    def update(self, package: AdminPackage, updates: dict) -> AdminPackage:
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
        self.db.query(AdminPackage).delete()
        self.db.commit()

