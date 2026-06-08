from uuid import UUID
from datetime import time
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enum import ListingType, CurrencyCode, BookingUnit, MediaType, StayStatus, ListingStatus, PropertyType
from app.models.listing import Listing
from app.models.hotelDetail import HotelDetail
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.models.listingMedia import ListingMedia
from app.models.stay import StayProperty
from app.repositories.stay_repo import StayRepository
from app.repositories.listing_repo import ListingRepository


class StayApprovalService:
    """Service for approving stay properties and converting them to marketplace listings"""
    
    def __init__(self, db: Session):
        self.db = db
        self.stay_repo = StayRepository(db)
        self.listing_repo = ListingRepository(db)
    
    def list_stays(self, status_filter: Optional[str] = None) -> Dict[str, Any]:
        """List stays optionally filtered by status"""
        if status_filter:
            try:
                status_enum = StayStatus(status_filter.upper())
            except ValueError:
                raise ValueError(f"Invalid status filter: {status_filter}")
            
            # Filter by specific status
            stays = self.db.query(StayProperty).filter(
                StayProperty.status == status_enum
            ).order_by(StayProperty.created_at.desc()).all()
        else:
            # Get all stays
            stays = self.stay_repo.list_all()
        
        properties = [self._build_stay_response(stay) for stay in stays]
        return {
            "properties": properties,
            "total": len(properties)
        }
    
    def _get_or_create_destination(self, stay_property: StayProperty):
        """Get or create destination from stay property"""
        destination_name = stay_property.city or stay_property.district or stay_property.address or "Sri Lanka"
        
        from app.models.destination import Destination
        from app.models.enum import DestinationType
        
        destination = (
            self.db.query(Destination)
            .filter(Destination.name == destination_name)
            .first()
        )
        if not destination:
            destination = Destination(
                name=destination_name,
                destination_type=DestinationType.CITY,
            )
            self.db.add(destination)
            self.db.flush()
            
        return destination

    def approve_stay(self, property_id: UUID) -> Dict[str, Any]:
        """Approve a stay property and publish linked listing"""
        # Load stay property with relationships
        stay_property = self.stay_repo.get_by_id(property_id)
        if not stay_property:
            raise ValueError("Stay property not found")
        
        if stay_property.status != StayStatus.SUBMITTED:
            raise ValueError(f"Stay property cannot be approved from status: {stay_property.status.value if hasattr(stay_property.status, 'value') else stay_property.status}")
        
        try:
            # If stay.listing_id is NULL:
            if not stay_property.listing_id:
                # 1. Resolve or create Destination
                destination = self._get_or_create_destination(stay_property)
                
                # 2. Determine base currency from room types
                currency = CurrencyCode.LKR
                if stay_property.room_types:
                    first_room = stay_property.room_types[0]
                    if first_room.currency:
                        try:
                            currency = CurrencyCode(first_room.currency.upper())
                        except ValueError:
                            currency = CurrencyCode.LKR
                
                # 3. Create Listing row
                listing = Listing(
                    destination_id=destination.id,
                    vendor_id=stay_property.vendor_id,
                    listing_type=ListingType.HOTEL,
                    title=stay_property.name,
                    slug=self._generate_slug(stay_property.name),
                    description=stay_property.description,
                    latitude=float(stay_property.latitude) if stay_property.latitude else None,
                    longitude=float(stay_property.longitude) if stay_property.longitude else None,
                    status=ListingStatus.PUBLISHED,
                    base_currency=currency,
                    is_active=True,
                )
                self.db.add(listing)
                self.db.flush()  # get listing.id
                
                # 4. Create HotelDetail linked to listing.id
                self._create_hotel_details(listing.id, stay_property)
                
                # 5. Create ListingVariant records from room types
                self._create_listing_variants(listing.id, stay_property)
                
                # 6. Create ListingMedia references from stay media
                self._create_listing_media(listing.id, stay_property)
                
                # 7. Set stay.listing_id = listing.id
                stay_property.listing_id = listing.id
                
            else:
                # If stay.listing_id already exists:
                existing_listing = self.listing_repo.get_by_id(stay_property.listing_id)
                if not existing_listing:
                    raise ValueError("Linked listing not found")
                
                # Update existing listing details
                destination = self._get_or_create_destination(stay_property)
                existing_listing.destination_id = destination.id
                existing_listing.title = stay_property.name
                existing_listing.description = stay_property.description
                existing_listing.latitude = float(stay_property.latitude) if stay_property.latitude else None
                existing_listing.longitude = float(stay_property.longitude) if stay_property.longitude else None
                existing_listing.status = ListingStatus.PUBLISHED
                
                # Update hotel details
                hotel_detail = self.db.query(HotelDetail).filter(HotelDetail.listing_id == existing_listing.id).first()
                hotel_detail_data = self._build_hotel_detail_data(existing_listing.id, stay_property)
                if hotel_detail:
                    for k, v in hotel_detail_data.items():
                        setattr(hotel_detail, k, v)
                else:
                    hotel_detail = HotelDetail(**hotel_detail_data)
                    self.db.add(hotel_detail)
                
                # Delete and re-create listing variants
                variants = self.db.query(ListingVariant).filter(ListingVariant.listing_id == existing_listing.id).all()
                for variant in variants:
                    self.db.delete(variant)
                self.db.flush()
                self._create_listing_variants(existing_listing.id, stay_property)
                
                # Delete and re-create listing media
                media_items = self.db.query(ListingMedia).filter(ListingMedia.listing_id == existing_listing.id).all()
                for item in media_items:
                    self.db.delete(item)
                self.db.flush()
                self._create_listing_media(existing_listing.id, stay_property)
            
            # Set stay status = APPROVED
            stay_property.status = StayStatus.APPROVED
            
            self.db.commit()
            
            return {
                "listing_id": str(stay_property.listing_id),
                "stay_id": str(property_id)
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to approve stay property: {str(e)}")
    
    def reject_stay(self, property_id: UUID) -> None:
        """Reject a stay property and update linked listing status"""
        stay_property = self.stay_repo.get_by_id(property_id)
        if not stay_property:
            raise ValueError("Stay property not found")
        
        if stay_property.status != StayStatus.SUBMITTED:
            raise ValueError(f"Stay property cannot be rejected from status: {stay_property.status.value if hasattr(stay_property.status, 'value') else stay_property.status}")
        
        try:
            # Update stay property status
            stay_property.status = StayStatus.REJECTED
            
            # Update linked listing status if it exists
            if stay_property.listing_id:
                listing = self.listing_repo.get_by_id(stay_property.listing_id)
                if listing:
                    listing.status = ListingStatus.REJECTED
            
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to reject stay property: {str(e)}")

    def _build_hotel_detail_data(self, listing_id: UUID, stay_property: StayProperty) -> Dict[str, Any]:
        """Build hotel detail dictionary from stay property"""
        policies = stay_property.policies or {}
        metadata = stay_property.metadata_json or {}
        contact = stay_property.contact or {}
        
        # FIX 1: Preserve rich amenity data instead of flattening to names only
        # Store structured amenity data with full details
        structured_amenities = []
        if stay_property.amenities:
            for amenity_map in stay_property.amenities:
                amenity = amenity_map.amenity
                structured_amenities.append({
                    "id": str(amenity.id),
                    "name": amenity.name,
                    "category": amenity.category,
                    "description": amenity.description,
                    "value_type": amenity.value_type,
                    "value": amenity_map.flattened_value
                })
        
        # FIX 2: Preserve room unit inventory data
        # Store room unit details since there's no public room inventory table
        room_inventory = []
        if stay_property.room_units:
            for room_unit in stay_property.room_units:
                room_inventory.append({
                    "id": str(room_unit.id),
                    "room_type_id": str(room_unit.room_type_id),
                    "room_number": room_unit.room_number,
                    "floor": room_unit.floor,
                    "room_name": room_unit.room_name,
                    "status": room_unit.status,
                    "metadata": room_unit.metadata_json or {}
                })
        
        # FIX 3: Remove hardcoded policy overrides - use actual stay data
        # Determine WiFi availability from amenities or policies
        wifi_available = any(
            amenity.amenity.name.lower() in ["wifi", "wi-fi", "internet", "wireless internet"] 
            for amenity in stay_property.amenities or []
        ) if stay_property.amenities else policies.get("wifi", None)
        
        # Determine pets policy from policies or amenities  
        pets_allowed = policies.get("petsAllowed", None)
        if pets_allowed is None:
            pets_allowed = any(
                "pet" in amenity.amenity.name.lower() or "animal" in amenity.amenity.name.lower()
                for amenity in stay_property.amenities or []
            ) if stay_property.amenities else False
            
        # Get smoking policy from policies or default appropriately
        smoking_policy = policies.get("smokingPolicy", "No smoking allowed")
        
        # Extract meal plans from policies or amenities
        meal_plans = policies.get("mealPlans", [])
        if not meal_plans and stay_property.amenities:
            meal_related_amenities = [
                amenity.amenity.name for amenity in stay_property.amenities
                if any(meal_word in amenity.amenity.name.lower() 
                      for meal_word in ["breakfast", "lunch", "dinner", "meal", "restaurant", "dining"])
            ]
            meal_plans = meal_related_amenities
        
        # FIX 6: Preserve rich room type details 
        # Store detailed room information since ListingVariant has limited fields
        room_type_details = {}
        if stay_property.room_types:
            for room_type in stay_property.room_types:
                room_type_details[str(room_type.id)] = {
                    "id": str(room_type.id),
                    "name": room_type.name,
                    "description": room_type.description,
                    "size": room_type.size,
                    "size_unit": room_type.size_unit,
                    "max_guests": room_type.max_guests,
                    "base_price": float(room_type.base_price) if room_type.base_price else None,
                    "currency": room_type.currency,
                    "bed_configuration": room_type.bed_configuration or {},
                    "bathroom": room_type.bathroom or {},
                    "discounts": room_type.discounts or [],
                    "metadata": room_type.metadata_json or {},
                    # Include room-level amenities/features from metadata
                    "smoking": room_type.metadata_json.get("smoking") if room_type.metadata_json else None,
                    "guest_access": room_type.metadata_json.get("guest_access") if room_type.metadata_json else None,
                }
        
        return {
            "listing_id": listing_id,
            "property_type": PropertyType(stay_property.property_type) if stay_property.property_type else PropertyType.HOTEL,
            "star_rating": metadata.get("star_rating", 3),
            "check_in_time": self._parse_time(policies.get("checkInTime", "14:00")),
            "check_out_time": self._parse_time(policies.get("checkOutTime", "11:00")),
            "child_policy": policies.get("childPolicy", "Children are welcome"),
            "property_name": stay_property.name,
            "short_location": stay_property.city or stay_property.district or "",
            "address_line_1": stay_property.address or "",
            "address_line_2": metadata.get("addressLine2", ""),
            "city": stay_property.city or "",
            "district": stay_property.district or "",
            "postal_code": metadata.get("postalCode", ""),
            "contact_phone": contact.get("phone", ""),
            "contact_email": contact.get("email", ""),
            "website": contact.get("website", ""),
            "google_map_url": contact.get("googleMapUrl", ""),
            # V2 STAY DATA: Store structured amenities with full details + room metadata in JSON
            # This preserves room inventory and room type details that don't fit in standard fields
            "amenities": structured_amenities + [
                {
                    "type": "room_inventory",
                    "data": room_inventory
                },
                {
                    "type": "room_type_details", 
                    "data": room_type_details
                }
            ] if (room_inventory or room_type_details) else structured_amenities,
            "languages_spoken": contact.get("languages", []),
            "room_count": len(stay_property.room_units) if stay_property.room_units else 0,
            "max_guest_capacity": self._calculate_max_capacity(stay_property),
            # V2 STAY DATA: Store meal plans from policies or derived from amenities
            "meal_plans": meal_plans,
            "parking_available": policies.get("parking", False),
            # FIX: Use actual WiFi data instead of hardcoded True
            "wifi_available": wifi_available if wifi_available is not None else True,
            # FIX: Use actual pets policy instead of hardcoded False
            "pets_allowed": pets_allowed,
            # FIX: Use actual smoking policy instead of hardcoded "No smoking" 
            "smoking_policy": smoking_policy,
            "cancellation_policy": policies.get("cancellationPolicy", "Free cancellation up to 24 hours before check-in"),
            "extra_bed_policy": policies.get("extraBedPolicy", "Extra beds available on request"),
            "check_in_notes": policies.get("checkInNotes", ""),
            "check_out_notes": policies.get("checkOutNotes", ""),
        }
    
    def _create_hotel_details(self, listing_id: UUID, stay_property: StayProperty) -> None:
        """Create hotel details from stay property"""
        hotel_detail_data = self._build_hotel_detail_data(listing_id, stay_property)
        
        # Remove fields that don't exist in HotelDetail model but store them separately for potential future use
        room_inventory = hotel_detail_data.pop("_room_inventory", None)
        room_type_details = hotel_detail_data.pop("_room_type_details", None)
        
        hotel_detail = HotelDetail(**hotel_detail_data)
        self.db.add(hotel_detail)
    
    def _create_listing_variants(self, listing_id: UUID, stay_property: StayProperty) -> None:
        """Create listing variants from room types with preserved room details and discount data"""
        for room_type in stay_property.room_types or []:
            variant_data = {
                "listing_id": listing_id,
                "name": room_type.name,
                "booking_unit": BookingUnit.PER_ROOM,
                "capacity_min": 1,
                "capacity_max": int(room_type.max_guests) if room_type.max_guests else 2,
                "is_default": False,
            }
            
            variant = ListingVariant(**variant_data)
            self.db.add(variant)
            self.db.flush()  # Get variant ID
            
            # FIX 4: Create base pricing rule from room base_price
            if room_type.base_price:
                base_pricing_data = {
                    "variant_id": variant.id,
                    "amount": Decimal(str(room_type.base_price)),
                    "currency": CurrencyCode(room_type.currency) if room_type.currency else CurrencyCode.LKR,
                    "min_guest": 1,
                    "max_guest": int(room_type.max_guests) if room_type.max_guests and room_type.max_guests.isdigit() else 2,
                    "priority": 1,
                }
                
                pricing_rule = PricingRule(**base_pricing_data)
                self.db.add(pricing_rule)
            
            # FIX 5: Create additional pricing rules from room discounts
            # Room discounts are critical business data that must be preserved
            if room_type.discounts:
                for i, discount in enumerate(room_type.discounts):
                    # Calculate discounted amount
                    discount_amount = None
                    if room_type.base_price and discount.get("value"):
                        base_price = Decimal(str(room_type.base_price))
                        
                        if discount.get("type") == "percentage":
                            discount_percent = Decimal(str(discount["value"]))
                            discount_amount = base_price * (Decimal("100") - discount_percent) / Decimal("100")
                        elif discount.get("type") == "fixed":
                            discount_value = Decimal(str(discount["value"]))
                            discount_amount = base_price - discount_value
                    
                    if discount_amount and discount_amount > 0:
                        # Create discount pricing rule with lower priority (higher number = lower priority)
                        discount_pricing_data = {
                            "variant_id": variant.id,
                            "amount": discount_amount,
                            "currency": CurrencyCode(room_type.currency) if room_type.currency else CurrencyCode.LKR,
                            "min_guest": 1,
                            "max_guest": int(room_type.max_guests) if room_type.max_guests and room_type.max_guests.isdigit() else 2,
                            "priority": 10 + i,  # Lower priority than base price
                            # V2 STAY DATA: Store discount details in pricing rule
                            # Since PricingRule doesn't have metadata, we'll store discount info with the variant
                        }
                        
                        discount_pricing_rule = PricingRule(**discount_pricing_data)
                        self.db.add(discount_pricing_rule)
    
    def _create_listing_media(self, listing_id: UUID, stay_property: StayProperty) -> None:
        """Create listing media from stay property media"""
        if not stay_property.media:
            return
        
        for index, media_item in enumerate(stay_property.media):
            if not media_item.get("url"):
                continue
                
            media_data = {
                "listing_id": listing_id,
                "media_type": MediaType.IMAGE,
                "url": media_item["url"],
                "alt_text": media_item.get("alt_text", f"{stay_property.name} - Image {index + 1}"),
                "sort_order": media_item.get("sortOrder", index + 1),
                "is_cover": media_item.get("role") == "cover",
            }
            
            listing_media = ListingMedia(**media_data)
            self.db.add(listing_media)
    
    def _calculate_max_capacity(self, stay_property: StayProperty) -> int:
        """Calculate maximum guest capacity from room types"""
        max_capacity = 0
        for room_type in stay_property.room_types or []:
            if room_type.max_guests:
                try:
                    capacity = int(room_type.max_guests)
                    max_capacity = max(max_capacity, capacity)
                except (ValueError, TypeError):
                    continue
        return max_capacity or 2  # Default to 2 if no capacity found
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object"""
        try:
            if ":" in time_str:
                hour, minute = time_str.split(":")[:2]
                return time(int(hour), int(minute))
            return time(14, 0)  # Default to 2:00 PM
        except (ValueError, TypeError):
            return time(14, 0)  # Default to 2:00 PM
    
    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title"""
        import re
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug[:50]  # Limit length
    
    def _build_stay_response(self, stay: StayProperty) -> Dict[str, Any]:
        """Build stay property response"""
        # Build location from address components
        location_parts = []
        if stay.address:
            location_parts.append(stay.address)
        if stay.city:
            location_parts.append(stay.city)
        if stay.district and stay.district != stay.city:
            location_parts.append(stay.district)
        location = ", ".join(location_parts) if location_parts else "Sri Lanka"
        
        # Get vendor name from relationship
        vendor_name = ""
        if hasattr(stay, 'vendor') and stay.vendor:
            vendor_name = stay.vendor.company_name or stay.vendor.first_name or "Unknown Vendor"
        else:
            # Fallback: query vendor directly if relationship not loaded
            from app.models.user import User
            vendor = self.db.query(User).filter(User.id == stay.vendor_id).first()
            if vendor:
                vendor_name = vendor.company_name or f"{vendor.first_name} {vendor.last_name}".strip() or "Unknown Vendor"
        
        # Get minimum price from room types
        price_per_night = 0
        if stay.room_types:
            prices = [float(rt.base_price) for rt in stay.room_types if rt.base_price and float(rt.base_price) > 0]
            price_per_night = min(prices) if prices else 0
        
        # Build policies from policies dict
        policies = stay.policies or {}
        policies_formatted = {
            "checkIn": policies.get("checkInTime", "2:00 PM"),
            "checkOut": policies.get("checkOutTime", "11:00 AM"), 
            "cancellationPolicy": policies.get("cancellationPolicy", "Standard cancellation policy"),
        }
        
        return {
            "id": str(stay.id),
            "name": stay.name,
            "propertyType": stay.property_type,
            "description": stay.description,
            "address": stay.address,
            "city": stay.city,
            "district": stay.district,
            "location": location,
            "status": stay.status,
            "listingId": str(stay.listing_id) if stay.listing_id else None,
            "vendorId": str(stay.vendor_id),
            "vendorName": vendor_name,
            "pricePerNight": price_per_night,
            "policies": policies_formatted,
            "createdAt": stay.created_at.isoformat() if stay.created_at else None,
            "updatedAt": stay.updated_at.isoformat() if stay.updated_at else None,
            "roomTypes": [
                {
                    "id": str(room_type.id),
                    "name": room_type.name,
                    "maxGuests": room_type.max_guests,
                    "basePrice": room_type.base_price,
                    "currency": room_type.currency,
                }
                for room_type in stay.room_types or []
            ],
            "amenities": [
                {"name": amenity.amenity.name}
                for amenity in stay.amenities or []
            ],
            "media": stay.media or [],
        }
