from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.admin_addon import AdminAddOn
from app.models.admin_package import AdminPackage
from app.models.admin_setting import AdminSetting
from app.models.enum import ListingType, UserRole
from app.models.guestReview import GuestReview
from app.models.listing import Listing
from app.models.reviewMetric import ReviewMetric
from app.models.room import Room
from app.models.user import User

router = APIRouter()

_CATEGORY_TO_TYPE = {
	"stay": ListingType.HOTEL,
	"tour": ListingType.TOUR,
	"activity": ListingType.ACTIVITY,
	"transfer": ListingType.TRANSPORT,
}


def require_admin(current_user: User = Depends(get_current_user)) -> User:
	if current_user.role != UserRole.ADMIN:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
	return current_user


def _build_settings(db: Session) -> dict:
	settings_row = db.query(AdminSetting).filter(AdminSetting.id == 1).first()
	if settings_row is None:
		settings_row = AdminSetting(id=1)
		db.add(settings_row)
		db.commit()
		db.refresh(settings_row)
	return {
		"siteName": settings_row.site_name,
		"contactEmail": settings_row.contact_email,
		"defaultCurrency": settings_row.default_currency,
	}


def _build_package_response(pkg: AdminPackage) -> dict:
	return {
		"id": str(pkg.id),
		"name": pkg.name,
		"description": pkg.description,
		"duration": pkg.duration,
		"route": pkg.route,
		"basePrice": pkg.base_price,
		"image": pkg.image,
		"category": pkg.category,
		"includes": pkg.includes or [],
		"itinerary": pkg.itinerary or [],
		"addOns": pkg.add_ons or [],
		"isActive": pkg.is_active,
	}


def _build_addon_response(addon: AdminAddOn) -> dict:
	return {
		"id": str(addon.id),
		"name": addon.name,
		"description": addon.description,
		"price": addon.price,
		"category": addon.category,
	}


def _build_listing_response(listing: Listing) -> dict:
	category = next((key for key, value in _CATEGORY_TO_TYPE.items() if value == listing.type), "tour")
	payload = {
		"id": str(listing.id),
		"category": category,
		"title": listing.title,
		"location": listing.location or "",
		"description": listing.description or "",
		"image": listing.image or "",
		"rating": listing.rating or 0,
		"reviewCount": listing.review_count or 0,
		"cancellationPolicy": listing.cancellation_policy or "",
		"includes": listing.includes or [],
		"recommendation": listing.recommendation or "",
		"isActive": listing.is_active,
		"duration": listing.duration,
		"route": listing.route,
		"price": listing.price,
		"highlights": listing.highlights or [],
		"activityType": listing.activity_type,
		"difficulty": listing.difficulty,
		"origin": listing.origin,
		"destination": listing.destination,
		"vehicleType": listing.vehicle_type,
		"serviceHighlights": listing.service_highlights or [],
	}
	if category == "stay":
		payload["rooms"] = [
			{
				"id": str(room.id),
				"name": room.name,
				"amenities": room.amenities or [],
				"pricePerNight": room.price_per_night,
				"available": room.available,
			}
			for room in listing.rooms
		]
		payload["reviewMetrics"] = [
			{
				"label": metric.label,
				"score": metric.score,
			}
			for metric in listing.review_metrics
		]
		payload["guestReviews"] = [
			{
				"id": str(review.id),
				"author": review.author,
				"quote": review.quote,
			}
			for review in listing.guest_reviews
		]

	return {key: value for key, value in payload.items() if value is not None}


@router.get("/snapshot")
async def get_snapshot(
	db: Session = Depends(get_db),
	_: User = Depends(require_admin),
):
	listings_by_category = {"stay": [], "tour": [], "activity": [], "transfer": []}
	listings = db.query(Listing).order_by(Listing.created_at.desc()).all()
	for listing in listings:
		response = _build_listing_response(listing)
		listings_by_category[response["category"]].append(response)

	return {
		"packages": [_build_package_response(pkg) for pkg in db.query(AdminPackage).order_by(AdminPackage.created_at.desc()).all()],
		"addOns": [_build_addon_response(addon) for addon in db.query(AdminAddOn).order_by(AdminAddOn.created_at.desc()).all()],
		"settings": _build_settings(db),
		"listings": listings_by_category,
	}


@router.post("/packages", status_code=status.HTTP_201_CREATED)
async def create_package(payload: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	pkg = AdminPackage(
		name=payload["name"],
		description=payload["description"],
		duration=payload["duration"],
		route=payload["route"],
		base_price=payload["basePrice"],
		image=payload["image"],
		category=payload["category"],
		includes=payload.get("includes", []),
		itinerary=payload.get("itinerary", []),
		add_ons=payload.get("addOns", []),
		is_active=payload.get("isActive", True),
	)
	db.add(pkg)
	db.commit()
	db.refresh(pkg)
	return _build_package_response(pkg)


@router.patch("/packages/{package_id}")
async def update_package(package_id: UUID, payload: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	pkg = db.query(AdminPackage).filter(AdminPackage.id == package_id).first()
	if pkg is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")

	field_map = {
		"name": "name",
		"description": "description",
		"duration": "duration",
		"route": "route",
		"basePrice": "base_price",
		"image": "image",
		"category": "category",
		"includes": "includes",
		"itinerary": "itinerary",
		"addOns": "add_ons",
		"isActive": "is_active",
	}
	for source, target in field_map.items():
		if source in payload:
			setattr(pkg, target, payload[source])

	db.commit()
	db.refresh(pkg)
	return _build_package_response(pkg)


@router.delete("/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(package_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	pkg = db.query(AdminPackage).filter(AdminPackage.id == package_id).first()
	if pkg is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
	db.delete(pkg)
	db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/packages/{package_id}/toggle-active")
async def toggle_package_active(package_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	pkg = db.query(AdminPackage).filter(AdminPackage.id == package_id).first()
	if pkg is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
	pkg.is_active = not pkg.is_active
	db.commit()
	db.refresh(pkg)
	return _build_package_response(pkg)


@router.post("/addons", status_code=status.HTTP_201_CREATED)
async def create_addon(payload: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	addon = AdminAddOn(
		name=payload["name"],
		description=payload["description"],
		price=payload["price"],
		category=payload["category"],
	)
	db.add(addon)
	db.commit()
	db.refresh(addon)
	return _build_addon_response(addon)


@router.delete("/addons/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_addon(addon_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	addon = db.query(AdminAddOn).filter(AdminAddOn.id == addon_id).first()
	if addon is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Add-on not found")

	db.delete(addon)
	db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/listings/{category}", status_code=status.HTTP_201_CREATED)
async def create_listing(category: str, payload: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	if category not in _CATEGORY_TO_TYPE:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported listing category")

	listing = Listing(
		type=_CATEGORY_TO_TYPE[category],
		title=payload["title"],
		description=payload.get("description"),
		location=payload.get("location"),
		image=payload.get("image"),
		rating=payload.get("rating"),
		review_count=payload.get("reviewCount"),
		cancellation_policy=payload.get("cancellationPolicy"),
		includes=payload.get("includes", []),
		recommendation=payload.get("recommendation"),
		is_active=payload.get("isActive", True),
		duration=payload.get("duration"),
		route=payload.get("route"),
		price=payload.get("price"),
		highlights=payload.get("highlights", []),
		activity_type=payload.get("activityType"),
		difficulty=payload.get("difficulty"),
		origin=payload.get("origin"),
		destination=payload.get("destination"),
		vehicle_type=payload.get("vehicleType"),
		service_highlights=payload.get("serviceHighlights", []),
	)
	db.add(listing)
	db.commit()
	db.refresh(listing)

	if category == "stay":
		for room_payload in payload.get("rooms", []):
			db.add(
				Room(
					listing_id=listing.id,
					name=room_payload["name"],
					amenities=room_payload.get("amenities", []),
					price_per_night=room_payload["pricePerNight"],
					available=room_payload.get("available", True),
				)
			)
		for metric_payload in payload.get("reviewMetrics", []):
			db.add(
				ReviewMetric(
					listing_id=listing.id,
					label=metric_payload["label"],
					score=metric_payload["score"],
				)
			)
		for review_payload in payload.get("guestReviews", []):
			db.add(
				GuestReview(
					listing_id=listing.id,
					author=review_payload["author"],
					quote=review_payload["quote"],
				)
			)
		db.commit()
		db.refresh(listing)

	return _build_listing_response(listing)


@router.patch("/listings/{category}/{listing_id}")
async def update_listing(
	category: str,
	listing_id: UUID,
	payload: dict,
	db: Session = Depends(get_db),
	_: User = Depends(require_admin),
):
	if category not in _CATEGORY_TO_TYPE:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported listing category")

	listing = db.query(Listing).filter(Listing.id == listing_id).first()
	if listing is None or listing.type != _CATEGORY_TO_TYPE[category]:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

	field_map = {
		"title": "title",
		"description": "description",
		"location": "location",
		"image": "image",
		"rating": "rating",
		"reviewCount": "review_count",
		"cancellationPolicy": "cancellation_policy",
		"includes": "includes",
		"recommendation": "recommendation",
		"isActive": "is_active",
		"duration": "duration",
		"route": "route",
		"price": "price",
		"highlights": "highlights",
		"activityType": "activity_type",
		"difficulty": "difficulty",
		"origin": "origin",
		"destination": "destination",
		"vehicleType": "vehicle_type",
		"serviceHighlights": "service_highlights",
	}
	for source, target in field_map.items():
		if source in payload:
			setattr(listing, target, payload[source])

	if category == "stay":
		if "rooms" in payload:
			db.query(Room).filter(Room.listing_id == listing.id).delete()
			for room_payload in payload.get("rooms", []):
				db.add(
					Room(
						listing_id=listing.id,
						name=room_payload["name"],
						amenities=room_payload.get("amenities", []),
						price_per_night=room_payload["pricePerNight"],
						available=room_payload.get("available", True),
					)
				)
		if "reviewMetrics" in payload:
			db.query(ReviewMetric).filter(ReviewMetric.listing_id == listing.id).delete()
			for metric_payload in payload.get("reviewMetrics", []):
				db.add(
					ReviewMetric(
						listing_id=listing.id,
						label=metric_payload["label"],
						score=metric_payload["score"],
					)
				)
		if "guestReviews" in payload:
			db.query(GuestReview).filter(GuestReview.listing_id == listing.id).delete()
			for review_payload in payload.get("guestReviews", []):
				db.add(
					GuestReview(
						listing_id=listing.id,
						author=review_payload["author"],
						quote=review_payload["quote"],
					)
				)

	db.commit()
	db.refresh(listing)
	return _build_listing_response(listing)


@router.delete("/listings/{category}/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(category: str, listing_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	if category not in _CATEGORY_TO_TYPE:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported listing category")
	listing = db.query(Listing).filter(Listing.id == listing_id).first()
	if listing is None or listing.type != _CATEGORY_TO_TYPE[category]:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

	db.query(Room).filter(Room.listing_id == listing.id).delete()
	db.query(ReviewMetric).filter(ReviewMetric.listing_id == listing.id).delete()
	db.query(GuestReview).filter(GuestReview.listing_id == listing.id).delete()
	db.delete(listing)
	db.commit()
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/settings")
async def update_settings(payload: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
	settings_row = db.query(AdminSetting).filter(AdminSetting.id == 1).first()
	if settings_row is None:
		settings_row = AdminSetting(id=1)
		db.add(settings_row)

	if "siteName" in payload:
		settings_row.site_name = payload["siteName"]
	if "contactEmail" in payload:
		settings_row.contact_email = payload["contactEmail"]
	if "defaultCurrency" in payload:
		settings_row.default_currency = payload["defaultCurrency"]

	db.commit()
	db.refresh(settings_row)
	return {
		"siteName": settings_row.site_name,
		"contactEmail": settings_row.contact_email,
		"defaultCurrency": settings_row.default_currency,
	}


@router.post("/reset")
async def reset_admin_data(db: Session = Depends(get_db), _: User = Depends(require_admin)):
	db.query(Room).delete()
	db.query(ReviewMetric).delete()
	db.query(GuestReview).delete()
	db.query(Listing).delete()
	db.query(AdminPackage).delete()
	db.query(AdminAddOn).delete()
	db.query(AdminSetting).delete()
	db.commit()
	return await get_snapshot(db=db, _=_)  # type: ignore[arg-type]
