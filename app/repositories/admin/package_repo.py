from uuid import UUID
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.admin_dashboard import Package, PackageAddOn

class AdminPackageRepository:
    def __init__(self, db: Session):
        self.db = db

    def _normalize_data(self, data: any) -> any:
        """Deeply normalizes dict keys to camelCase for consistent DB storage."""
        if isinstance(data, list):
            return [self._normalize_data(x) for x in data]
        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                if isinstance(k, str):
                    # Convert snake_case to camelCase
                    components = k.split("_")
                    new_key = components[0] + "".join(x.title() for x in components[1:])
                    new_dict[new_key] = self._normalize_data(v)
                else:
                    new_dict[k] = self._normalize_data(v)
            return new_dict
        return data

    def create(self, package_data: dict) -> Package:
        # Normalize JSON fields to camelCase before saving
        for field in ["quick_facts", "destinations", "itinerary", "structured_itinerary", "listing_refs", "highlights", "exclusions"]:
            if field in package_data and package_data[field] is not None:
                package_data[field] = self._normalize_data(package_data[field])

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
        # Normalize JSON fields to camelCase before saving
        for field in ["quick_facts", "destinations", "itinerary", "structured_itinerary", "listing_refs", "highlights", "exclusions"]:
            if field in updates and updates[field] is not None:
                updates[field] = self._normalize_data(updates[field])

        add_on_ids = updates.pop("add_ons", None)
        for key, value in updates.items():
            setattr(package, key, value)

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
