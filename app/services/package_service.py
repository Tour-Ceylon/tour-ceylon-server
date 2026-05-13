from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.admin.package_repo import AdminPackageRepository


def _normalize_addon_category(raw: str) -> str:
    return raw.strip().lower().replace("_", "-") if isinstance(raw, str) else str(raw)


def _deep_camel_case(obj):
    if isinstance(obj, list):
        return [_deep_camel_case(x) for x in obj]
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            if isinstance(k, str):
                components = k.split("_")
                new_key = components[0] + "".join(x.title() for x in components[1:])
                new_dict[new_key] = _deep_camel_case(v)
            else:
                new_dict[k] = _deep_camel_case(v)
        return new_dict
    return obj


def build_package_response(package) -> dict:
    add_on_values: list[str] = []
    add_on_details: list[dict] = []

    for link in getattr(package, "add_ons", []) or []:
        nested = getattr(link, "add_on", None)
        if nested is not None:
            add_on_values.append(str(nested.id))
            add_on_details.append({
                "id": str(nested.id),
                "name": nested.name,
                "description": nested.description,
                "price": nested.price,
                "category": _normalize_addon_category(getattr(nested.category, "value", nested.category)),
            })
        else:
            raw_id = getattr(link, "add_on_id", None)
            if raw_id is not None:
                add_on_values.append(str(raw_id))
            elif isinstance(link, str):
                add_on_values.append(link)

    category = getattr(package.category, "value", package.category)
    if isinstance(category, str):
        category = category.lower().replace("_", "-")

    res = {
        "id": package.id,
        "name": package.name,
        "summary": getattr(package, "summary", None),
        "description": package.description,
        "duration": package.duration,
        "nights": getattr(package, "nights", None),
        "route": package.route,
        "startLocation": getattr(package, "start_location", None),
        "endLocation": getattr(package, "end_location", None),
        "tripStyle": getattr(package, "trip_style", None),
        "vendorId": str(getattr(package, "vendor_id", None)) if getattr(package, "vendor_id", None) else None,
        "basePrice": package.base_price,
        "category": category,
        "includes": package.includes or [],
        "exclusions": getattr(package, "exclusions", []) or [],
        "highlights": getattr(package, "highlights", []) or [],
        "quickFacts": _deep_camel_case(getattr(package, "quick_facts", {}) or {}),
        "destinations": _deep_camel_case(getattr(package, "destinations", []) or []),
        "itinerary": _deep_camel_case(getattr(package, "derived_simple_itinerary", package.itinerary) or []),
        "structuredItinerary": _deep_camel_case(getattr(package, "normalized_structured_itinerary", []) or []),
        "listingRefs": _deep_camel_case(getattr(package, "listing_refs", []) or []),
        "addOns": add_on_values,
        "addOnDetails": add_on_details,
        "isActive": package.is_active,
        "cover_image": package.cover_image,
        "gallery": package.gallery,
    }
    return res


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
