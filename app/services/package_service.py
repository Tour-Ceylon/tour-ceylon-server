from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.admin.package_repo import AdminPackageRepository


def build_package_response(package) -> dict:
    add_on_values = []
    for add_on in getattr(package, "add_ons", []) or []:
        add_on_id = getattr(add_on, "add_on_id", None)
        if add_on_id is not None:
            add_on_values.append(str(add_on_id))
            continue

        nested_add_on = getattr(add_on, "add_on", None)
        nested_add_on_id = getattr(nested_add_on, "id", None)
        if nested_add_on_id is not None:
            add_on_values.append(str(nested_add_on_id))
            continue

        if isinstance(add_on, str):
            add_on_values.append(add_on)

    category = getattr(package.category, "value", package.category)
    if isinstance(category, str):
        category = category.lower().replace("_", "-")

    return {
        "id": package.id,
        "name": package.name,
        "description": package.description,
        "duration": package.duration,
        "route": package.route,
        "basePrice": package.base_price,
        "image": package.image,
        "category": category,
        "includes": package.includes or [],
        "itinerary": package.itinerary or [],
        "addOns": add_on_values,
        "isActive": package.is_active,
    }


class PackageService:
    def __init__(self, db: Session):
        self.packages = AdminPackageRepository(db)

    def get_active_packages(self) -> list[dict]:
        return [build_package_response(package) for package in self.packages.get_all_active()]

    def get_active_package(self, package_id: UUID) -> dict:
        package = self.packages.get_active(package_id)
        if package is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found",
            )
        return build_package_response(package)
