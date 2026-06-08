from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.destination import Destination
from app.models.enum import UserRole, ListingType, ListingStatus, DestinationType
from app.models.user import User
from app.repositories.listing_repo import ListingRepository
from app.schemas.listing_schema import ListingCreate, ListingResponse

router = APIRouter()


def get_listing_repository(db: Session = Depends(get_db)) -> ListingRepository:
    return ListingRepository(db)


def require_listing_vendor(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}:
        return current_user
    if role != UserRole.VENDOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only vendors or admins can manage listings"
        )
    return current_user


@router.post("/{category}", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_listing(
    category: str,
    payload: dict,
    current_user: User = Depends(require_listing_vendor),
    repo: ListingRepository = Depends(get_listing_repository),
    db: Session = Depends(get_db),
):
    """Create a new listing for vendor"""
    
    # Map category string to ListingType enum
    category_mapping = {
        "Stay": ListingType.HOTEL,
        "Tour": ListingType.TOUR, 
        "Safari": ListingType.SAFARI,
        "Experience": ListingType.EXPERIENCE,
        "Transfer": ListingType.TRANSFER,
    }
    
    listing_type = category_mapping.get(category)
    if not listing_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {category}"
        )

    # Check vendor approval for this category
    categories = current_user.approved_categories or []
    if category not in categories and current_user.role.value not in {UserRole.ADMIN.value, UserRole.SUPPORT.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vendor is not approved for {category} listings"
        )

    try:
        # DEBUG: Log the incoming payload
        print(f"DEBUG - Incoming payload for {category}: {payload}")
        
        # Convert frontend payload to backend schema
        listing_data = convert_frontend_payload_to_listing_create(payload, listing_type, db)
        
        # DEBUG: Log the converted listing_data
        print(f"DEBUG - Converted listing_data: {listing_data}")
        
        # Create the listing
        listing = repo.create(listing_data)
        return listing
        
    except ValueError as exc:
        print(f"DEBUG - ValueError: {str(exc)}")
        print(f"DEBUG - Payload causing error: {payload}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        print(f"DEBUG - Exception type: {type(exc).__name__}")
        print(f"DEBUG - Exception message: {str(exc)}")
        print(f"DEBUG - Payload causing error: {payload}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to create listing"
        ) from exc


def convert_frontend_payload_to_listing_create(payload: dict, listing_type: ListingType, db: Session) -> ListingCreate:
    """Convert frontend ListingEditor payload to ListingCreate schema"""
    
    # Get or create destination - try multiple sources for Stay listings
    destination_text = payload.get("destination", "").strip()
    
    # For Stay/Hotel listings, try multiple fallback sources
    if not destination_text and listing_type == ListingType.HOTEL:
        category_data = payload.get("categoryData", {})
        property_details = category_data.get("propertyDetails", {})
        
        # Try propertyLocation first
        destination_text = property_details.get("propertyLocation", "").strip()
        
        # Try other potential location fields
        if not destination_text:
            destination_text = property_details.get("propertyName", "").strip()
        if not destination_text:
            destination_text = category_data.get("address", "").strip()
        if not destination_text:
            destination_text = category_data.get("city", "").strip()
    
    # DEBUG: Show what destination sources we found
    print(f"DEBUG - Destination resolution for {listing_type}:")
    print(f"  - payload.destination: '{payload.get('destination', '')}'")
    if listing_type == ListingType.HOTEL:
        category_data = payload.get("categoryData", {})
        property_details = category_data.get("propertyDetails", {})
        print(f"  - propertyLocation: '{property_details.get('propertyLocation', '')}'")
        print(f"  - propertyName: '{property_details.get('propertyName', '')}'")
        print(f"  - Final destination_text: '{destination_text}'")
    
    if not destination_text:
        # Provide more detailed error for Stay listings
        if listing_type == ListingType.HOTEL:
            raise ValueError("Destination is required. Please provide either a destination or property location in the property details.")
        raise ValueError("Destination is required")
    
    destination = get_destination_by_name_or_create(db, destination_text)
    
    # Determine status based on save action
    is_draft = payload.get("action") == "save_draft"
    status = ListingStatus.DRAFT if is_draft else ListingStatus.PUBLISHED  # Use PUBLISHED instead of PENDING_REVIEW
    
    # Base listing data
    listing_data = {
        "listing_type": listing_type,
        "destination_id": destination.id,
        "title": payload.get("title", "").strip(),
        "description": payload.get("description", "").strip() or None,
        "latitude": float(payload["lat"]) if payload.get("lat") and payload["lat"].strip() else None,
        "longitude": float(payload["lng"]) if payload.get("lng") and payload["lng"].strip() else None,
        "status": status,
        "is_active": payload.get("active", True),
        "base_currency": "LKR",  # Default, will be overridden by variant currency
    }
    
    # Add category-specific detail data
    category_data = payload.get("categoryData", {})
    
    if listing_type == ListingType.HOTEL:
        listing_data["hotel_detail"] = convert_stay_detail(payload, category_data)
        listing_data["base_currency"] = "LKR"  # Stay uses LKR typically
    elif listing_type == ListingType.TOUR:
        listing_data["tour_detail"] = convert_tour_detail(payload, category_data)
    elif listing_type == ListingType.SAFARI:
        listing_data["safari_detail"] = convert_safari_detail(payload, category_data)
    elif listing_type == ListingType.EXPERIENCE:
        listing_data["activity_detail"] = convert_activity_detail(payload, category_data)
    elif listing_type == ListingType.TRANSFER:
        listing_data["transfer_detail"] = convert_transfer_detail(payload, category_data)
    
    # Convert variants and pricing
    variants = payload.get("variants", [])
    if variants:
        listing_data["variants"] = convert_variants(variants, listing_type)
        # Set base currency from first variant
        listing_data["base_currency"] = variants[0].get("currency", "USD")
    elif listing_type == ListingType.HOTEL:
        # For Stay/Hotel, create variants from room types if no explicit variants
        room_types = category_data.get("roomTypes", [])
        if room_types:
            listing_data["variants"] = convert_room_types_to_variants(room_types)
        else:
            # Ensure HOTEL listings always have at least one variant
            listing_data["variants"] = [{
                "name": "Standard Room",
                "booking_unit": "per_room",
                "capacity_min": 1,
                "capacity_max": 2,
                "is_default": True,
                "pricing": {
                    "amount": 100.0,
                    "currency": "LKR",
                    "priority": 1,
                }
            }]
    
    # Convert media
    media_data = convert_media(payload, category_data)
    if media_data:
        listing_data["media"] = media_data
        
    return ListingCreate(**listing_data)


def get_destination_by_name_or_create(db: Session, destination_name: str) -> Destination:
    """Get destination by name or create if it doesn't exist"""
    destination = db.query(Destination).filter(Destination.name == destination_name).first()
    if not destination:
        destination = Destination(
            name=destination_name,
            destination_type=DestinationType.CITY,  # Default type
        )
        db.add(destination)
        db.flush()
    return destination


def convert_stay_detail(payload: dict, category_data: dict) -> dict:
    """Convert Stay category data to hotel_detail schema"""
    from datetime import time
    from app.models.enum import PropertyType
    
    property_details = category_data.get("propertyDetails", {})
    
    # Convert time strings to time objects
    def parse_time(time_str: str, default_time: time) -> time:
        if not time_str:
            return default_time
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour=hour, minute=minute)
        except (ValueError, AttributeError):
            return default_time
    
    return {
        "property_type": PropertyType.HOTEL,  # Use enum value
        "star_rating": 3,  # Default, should be collected in frontend
        "check_in_time": parse_time(property_details.get("checkInTime", ""), time(14, 0)),  # 2:00 PM
        "check_out_time": parse_time(property_details.get("checkOutTime", ""), time(12, 0)),  # 12:00 PM
        "property_name": property_details.get("propertyName", payload.get("title", "")),
        "short_location": property_details.get("propertyLocation", payload.get("destination", "")),
        "amenities": category_data.get("amenities", []),
        "languages_spoken": property_details.get("languages", []),
        "parking_available": property_details.get("parking", False),
        "child_policy": category_data.get("ratePlans", {}).get("childPolicy"),
        "cancellation_policy": category_data.get("ratePlans", {}).get("standardCancellationPolicy"),
    }


def convert_tour_detail(payload: dict, category_data: dict) -> dict:
    """Convert Tour category data to tour_detail schema"""
    return {
        "duration_days": 1,  # Default, should be collected in frontend
        "route_summary": payload.get("description", "Tour route summary"),
        "meeting_point": payload.get("destination", "Meeting point TBD"),
        "itinerary_highlights": [],
        "included_items": [],
        "excluded_items": [],
        "languages": ["English"],
        "difficulty_level": "Easy",
        "group_size_min": 2,
        "group_size_max": 12,
        "private_available": True,
        "pickup_available": True,
        "dropoff_available": True,
    }


def convert_safari_detail(payload: dict, category_data: dict) -> dict:
    """Convert Safari category data to safari_detail schema"""
    from app.models.enum import SafariType
    
    return {
        "national_park": payload.get("destination", "National Park"),
        "safari_type": SafariType.FULL_DAY,  # Use enum value
        "duration_minutes": 240,  # 4 hours default
        "guide_included": True,
        "pickup_supported": True,
        "included_items": [],
        "excluded_items": [],
        "languages": ["English"],
        "difficulty_level": "Easy",
        "group_size_min": 2,
        "group_size_max": 6,
        "private_available": True,
        "what_to_bring": [],
        "wildlife_highlights": [],
    }


def convert_activity_detail(payload: dict, category_data: dict) -> dict:
    """Convert Experience category data to activity_detail schema"""
    return {
        "activity_type": "Adventure",  # Default, should be collected in frontend
        "duration_minutes": 180,  # 3 hours default
        "meeting_point": payload.get("destination", "Meeting point TBD"),
        "included_items": [],
        "excluded_items": [],
        "languages": ["English"],
        "difficulty_level": "Moderate",
        "group_size_min": 2,
        "group_size_max": 10,
        "private_available": True,
        "pickup_supported": True,
        "what_to_bring": [],
        "highlights": [],
    }


def convert_transfer_detail(payload: dict, category_data: dict) -> dict:
    """Convert Transfer category data to transfer_detail schema"""
    from app.models.enum import TransferLocationType, DestinationType
    
    return {
        "origin_type": TransferLocationType.AIRPORT,  # Use enum value
        "destination_type": DestinationType.HOTEL_ZONE,  # Use enum value  
        "vehicle_policy": "Standard transfer policy",
        "vehicle_types": ["Car", "Van"],
        "max_passengers": 4,
        "air_conditioned": True,
        "meet_and_greet_included": True,
        "child_seats_available": True,
        "estimated_duration_minutes": 60,
        "included_items": [],
        "excluded_items": [],
    }


def convert_variants(variants: list, listing_type: ListingType = None) -> list:
    """Convert frontend variants to backend variant schema"""
    converted = []
    
    for variant in variants:
        # Helper function to safely convert to int
        def safe_int(value, default):
            if not value or (isinstance(value, str) and not value.strip()):
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        # Helper function to safely convert to float
        def safe_float(value, default):
            if not value or (isinstance(value, str) and not value.strip()):
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # For hotel listings, force booking unit to be per_room
        if listing_type == ListingType.HOTEL:
            booking_unit = "per_room"
        else:
            booking_unit = map_booking_unit(variant.get("unit", "Per Person"))
        
        converted.append({
            "name": variant.get("name", "Default Package"),
            "booking_unit": booking_unit,
            "capacity_min": safe_int(variant.get("minCapacity"), 1),
            "capacity_max": safe_int(variant.get("maxCapacity"), 6),
            "is_default": variant.get("isDefault", False),
            "pricing": {
                "amount": safe_float(variant.get("price"), 0),
                "currency": variant.get("currency", "USD"),
                "priority": variant.get("priority", 1),
            }
        })
    
    return converted


def convert_room_types_to_variants(room_types: list) -> list:
    """Convert Stay room types to variants for hotel listings"""
    converted = []
    
    # Helper function to safely convert to int
    def safe_int(value, default):
        if not value or (isinstance(value, str) and not value.strip()):
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Helper function to safely convert to float
    def safe_float(value, default):
        if not value or (isinstance(value, str) and not value.strip()):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    for i, room in enumerate(room_types):
        converted.append({
            "name": room.get("type", f"Room {i+1}"),
            "booking_unit": "per_room",
            "capacity_min": 1,
            "capacity_max": safe_int(room.get("maxGuests"), 2),
            "is_default": i == 0,  # First room is default
            "pricing": {
                "amount": safe_float(room.get("pricePerNight"), 0),
                "currency": room.get("currency", "LKR"),
                "priority": i + 1,
            }
        })
    
    return converted


def convert_media(payload: dict, category_data: dict) -> list:
    """Convert frontend media to backend media schema"""
    media_list = []
    
    # Handle Stay category media
    if "images" in category_data:
        images = category_data["images"]
        cover = images.get("cover", "")
        gallery = images.get("gallery", [])
        
        if cover:
            media_list.append({
                "url": cover,
                "alt_text": f"{payload.get('title', 'Cover')} - Cover Image",
                "sort_order": 0,
                "is_cover": True,
                "media_type": "IMAGE"
            })
        
        for i, url in enumerate(gallery):
            media_list.append({
                "url": url,
                "alt_text": f"{payload.get('title', 'Gallery')} - Image {i+1}",
                "sort_order": i + 1,
                "is_cover": False,
                "media_type": "IMAGE"
            })
    
    return media_list


def map_booking_unit(unit_text: str) -> str:
    """Map frontend booking unit text to backend enum"""
    unit_mapping = {
        "Per Person": "per_person",
        "Per Group": "per_group",
        "Per Room": "per_room",
        "Per Vehicle": "per_vehicle",
    }
    return unit_mapping.get(unit_text, "per_person")
