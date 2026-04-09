from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.admin_dashboard import Package, PackageAddOn


class AdminPackageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, package_data: dict) -> Package:
        add_on_ids = package_data.pop("add_ons", []) or []
        package = Package(**package_data)
        self.db.add(package)
        for add_on_id in add_on_ids:
            package.add_ons.append(PackageAddOn(add_on_id=self._to_uuid(add_on_id)))
        self.db.commit()
        self.db.refresh(package)
        return package

    def get_all(self) -> list[Package]:
        return (
            self.db.query(Package)
            .options(joinedload(Package.cover_media), selectinload(Package.media_assets))
            .order_by(Package.created_at.desc())
            .all()
        )

    def get_all_active(self) -> list[Package]:
        return (
            self.db.query(Package)
            .options(joinedload(Package.cover_media), selectinload(Package.media_assets))
            .filter(Package.is_active.is_(True))
            .order_by(Package.created_at.desc())
            .all()
        )

    def get(self, package_id: UUID) -> Package | None:
        return (
            self.db.query(Package)
            .options(joinedload(Package.cover_media), selectinload(Package.media_assets))
            .filter(Package.id == package_id)
            .first()
        )

    def get_active(self, package_id: UUID) -> Package | None:
        return (
            self.db.query(Package)
            .options(joinedload(Package.cover_media), selectinload(Package.media_assets))
            .filter(Package.id == package_id, Package.is_active.is_(True))
            .first()
        )

    def update(self, package: Package, updates: dict) -> Package:
        add_on_ids = updates.pop("add_ons", None)
        for field, value in updates.items():
            setattr(package, field, value)

        if add_on_ids is not None:
            package.add_ons.clear()
            for add_on_id in add_on_ids:
                package.add_ons.append(PackageAddOn(add_on_id=self._to_uuid(add_on_id)))

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

    def _to_uuid(self, value: UUID | str) -> UUID:
        return value if isinstance(value, UUID) else UUID(value)

    def update_cover_media(self, package: Package, media_id: UUID | None) -> Package:
        package.cover_media_id = media_id
        self.db.flush()
        return package
