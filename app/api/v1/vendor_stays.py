from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.api.deps import get_current_user
from app.config.database import get_db
from app.integrations.cloudinary import CloudinaryIntegrationError
from app.models.enum import UserRole, StayStatus, AvailabilityStatus
from app.models.user import User
from app.models.stay import StayProperty
from app.models.listingVariant import ListingVariant
from app.models.availabilityCalendar import AvailabilityCalendar
from app.repositories.stay_repo import StayRepository
from app.schemas.stay_schema import StayPropertyCreate, StayPropertyListResponse, StayPropertyResponse
from app.schemas.availability_schema import (
    AvailabilityCreate,
    AvailabilityUpdate,
    AvailabilityResponse,
    AvailabilityListResponse,
)


router = APIRouter()


def get_stay_repository(db: Session = Depends(get_db)) -> StayRepository:
    return StayRepository(db)


def require_stay_vendor(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    categories = current_user.approved_categories or []
    if role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}:
        return current_user
    if role != UserRole.VENDOR.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only vendors or admins can manage stay applications")
    if "Stay" not in categories:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor is not approved for Stay listings")
    return current_user


def is_admin_user(user: User) -> bool:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}


@router.post("/", response_model=StayPropertyResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def create_stay_property(
    payload: StayPropertyCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    try:
        return repo.create_for_vendor(current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to upload stay images") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save stay application") from exc


@router.get("/", response_model=StayPropertyListResponse, response_model_by_alias=True)
async def list_stay_properties(
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    try:
        properties = repo.list_all() if is_admin_user(current_user) else repo.list_for_vendor(current_user.id)
        
        # Validate each property before adding to response
        validated_properties = []
        for prop in properties:
            try:
                validated_prop = StayPropertyResponse.model_validate(prop)
                validated_properties.append(validated_prop)
            except Exception as e:
                # Log the problematic property but don't fail the entire request
                print(f"Warning: Skipping invalid property {prop.id}: {str(e)}")
                continue
        
        return StayPropertyListResponse(properties=validated_properties, total=len(validated_properties))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to list stay properties: {str(exc)}") from exc


@router.get("/{property_id}", response_model=StayPropertyResponse, response_model_by_alias=True)
async def get_stay_property(
    property_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    property_record = repo.get_by_id(property_id) if is_admin_user(current_user) else repo.get_for_vendor(current_user.id, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found")
    return property_record


@router.put("/{property_id}", response_model=StayPropertyResponse, response_model_by_alias=True)
async def update_stay_property(
    property_id: UUID,
    payload: StayPropertyCreate,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    try:
        updated_property = repo.update_for_vendor(current_user.id, property_id, payload)
        if updated_property is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found or access denied")
        return updated_property
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CloudinaryIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to upload stay images") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update stay property") from exc


@router.delete("/{property_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def delete_stay_property(
    property_id: UUID,
    hard_delete: bool = False,
    reason: str = None,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    """
    Delete or archive a stay property.
    By default performs soft delete (archive). Use hard_delete=true for permanent deletion (DRAFT only).
    """
    try:
        if hard_delete:
            # Permanent deletion - only allowed for DRAFT stays
            deleted_property = repo.delete_for_vendor(current_user.id, property_id)
            if deleted_property is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found or access denied")
            return {"message": "Stay property permanently deleted", "property_id": str(property_id)}
        else:
            # Soft delete (archive)
            archived_property = repo.archive_for_vendor(current_user.id, property_id, reason)
            if archived_property is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found or access denied")
            return {
                "message": "Stay property archived successfully", 
                "property_id": str(property_id),
                "status": archived_property.status.value
            }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete stay property") from exc


@router.patch("/{property_id}/status", response_model=StayPropertyResponse, response_model_by_alias=True)
async def update_stay_status(
    property_id: UUID,
    new_status: str,
    current_user: User = Depends(require_stay_vendor),
    repo: StayRepository = Depends(get_stay_repository),
):
    """
    Update stay property status. Vendors can transition between DRAFT <-> SUBMITTED.
    Admin approval required for APPROVED/REJECTED status.
    """
    try:
        # Get existing property to check current state
        existing_property = repo.get_for_vendor(current_user.id, property_id)
        if not existing_property:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found or access denied")
        
        # Validate status transition
        new_status_upper = new_status.upper()
        current_status = existing_property.status.value.upper()
        
        # Allow vendors to transition between DRAFT and SUBMITTED only
        if new_status_upper not in ["DRAFT", "SUBMITTED"]:
            raise ValueError("Vendors can only set status to DRAFT or SUBMITTED")
        
        # Update status directly on the model
        from app.models.enum import StayStatus
        if new_status_upper == "DRAFT":
            existing_property.status = StayStatus.DRAFT
        elif new_status_upper == "SUBMITTED":
            existing_property.status = StayStatus.SUBMITTED
        
        repo.db.commit()
        
        # Return updated property
        return repo.get_for_vendor(current_user.id, property_id)
        
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update stay status") from exc


# Helper to validate ownership, approval status, listing existence, and variant ownership
def validate_vendor_stay_and_get_variants(
    db: Session,
    stay_property_id: UUID,
    current_user: User,
) -> list[UUID]:
    # 1. Fetch the stay property
    stay = db.query(StayProperty).filter(StayProperty.id == stay_property_id).first()
    if not stay:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay property not found")
    
    # 2. Check ownership (unless admin/support)
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    is_admin = role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}
    if not is_admin and stay.vendor_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You do not own this stay property")
        
    # 3. Check approval status
    if stay.status != StayStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stay property must be APPROVED to manage availability")
        
    # 4. Check listing_id
    if not stay.listing_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stay property must have a linked listing to manage availability")
        
    # 5. Fetch all variants under stay's listing_id and return their IDs
    variants = db.query(ListingVariant).filter(ListingVariant.listing_id == stay.listing_id).all()
    variant_ids = [v.id for v in variants]
    return variant_ids


@router.get("/{stay_property_id}/availability", response_model=AvailabilityListResponse)
async def list_availability(
    stay_property_id: UUID,
    variant_id: UUID | None = None,
    current_user: User = Depends(require_stay_vendor),
    db: Session = Depends(get_db),
):
    # Authorization and variants fetch
    allowed_variant_ids = validate_vendor_stay_and_get_variants(db, stay_property_id, current_user)
    
    query = db.query(AvailabilityCalendar).filter(AvailabilityCalendar.variant_id.in_(allowed_variant_ids))
    
    if variant_id:
        if variant_id not in allowed_variant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provided variant_id does not belong to this stay property")
        query = query.filter(AvailabilityCalendar.variant_id == variant_id)
        
    results = query.order_by(AvailabilityCalendar.service_date.asc()).all()
    return AvailabilityListResponse(availability=results, total=len(results))


@router.post("/{stay_property_id}/availability", response_model=list[AvailabilityResponse])
async def create_availability(
    stay_property_id: UUID,
    payload: AvailabilityCreate,
    current_user: User = Depends(require_stay_vendor),
    db: Session = Depends(get_db),
):
    # Authorization and variants fetch
    allowed_variant_ids = validate_vendor_stay_and_get_variants(db, stay_property_id, current_user)
    
    if payload.variant_id not in allowed_variant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provided variant_id does not belong to this stay property")
    
    # Date range generation
    from datetime import timedelta, datetime, timezone
    start = payload.start_date
    end = payload.end_date
    if start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="startDate must be less than or equal to endDate")
        
    delta = end - start
    created_or_updated = []
    
    for i in range(delta.days + 1):
        current_date = start + timedelta(days=i)
        dt_val = datetime(current_date.year, current_date.month, current_date.day, tzinfo=timezone.utc)
        
        # Check if row exists for this variant and date
        from sqlalchemy import cast, Date
        existing_row = db.query(AvailabilityCalendar).filter(
            AvailabilityCalendar.variant_id == payload.variant_id,
            cast(AvailabilityCalendar.service_date, Date) == current_date
        ).first()
        
        reserved_cap = 0
        if existing_row:
            reserved_cap = existing_row.reserved_capacity
            # Update row
            # Recalculate available capacity
            available_cap = payload.total_capacity - reserved_cap
            if available_cap < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"totalCapacity ({payload.total_capacity}) cannot be less than reservedCapacity ({reserved_cap}) for date {current_date}"
                )
            
            existing_row.total_capacity = payload.total_capacity
            existing_row.available_capacity = available_cap
            
            # Status calculation
            if available_cap <= 0:
                existing_row.available_status = AvailabilityStatus.SOLD_OUT
            else:
                existing_row.available_status = payload.available_status
                
            db.add(existing_row)
            created_or_updated.append(existing_row)
        else:
            # Create new row
            available_cap = payload.total_capacity
            status_val = payload.available_status
            if available_cap <= 0:
                status_val = AvailabilityStatus.SOLD_OUT
                
            new_row = AvailabilityCalendar(
                variant_id=payload.variant_id,
                service_date=dt_val,
                total_capacity=payload.total_capacity,
                reserved_capacity=0,
                available_capacity=available_cap,
                available_status=status_val
            )
            db.add(new_row)
            created_or_updated.append(new_row)
            
    try:
        db.commit()
        for row in created_or_updated:
            db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save availability records") from exc
        
    return created_or_updated


@router.put("/{stay_property_id}/availability/{availability_id}", response_model=AvailabilityResponse)
async def update_availability(
    stay_property_id: UUID,
    availability_id: UUID,
    payload: AvailabilityUpdate,
    current_user: User = Depends(require_stay_vendor),
    db: Session = Depends(get_db),
):
    # Authorization and variants fetch
    allowed_variant_ids = validate_vendor_stay_and_get_variants(db, stay_property_id, current_user)
    
    # Get availability record
    availability = db.query(AvailabilityCalendar).filter(AvailabilityCalendar.id == availability_id).first()
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability record not found")
        
    if availability.variant_id not in allowed_variant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Availability record does not belong to this stay property")
        
    # Check total_capacity < reserved_capacity
    if payload.total_capacity < availability.reserved_capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"totalCapacity ({payload.total_capacity}) cannot be less than reservedCapacity ({availability.reserved_capacity})"
        )
        
    # Recalculate available capacity
    available_cap = payload.total_capacity - availability.reserved_capacity
    availability.total_capacity = payload.total_capacity
    availability.available_capacity = available_cap
    
    # Status calculation
    if available_cap <= 0:
        availability.available_status = AvailabilityStatus.SOLD_OUT
    else:
        availability.available_status = payload.available_status
        
    try:
        db.commit()
        db.refresh(availability)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update availability record") from exc
        
    return availability


@router.delete("/{stay_property_id}/availability/{availability_id}", response_model=dict)
async def delete_availability(
    stay_property_id: UUID,
    availability_id: UUID,
    current_user: User = Depends(require_stay_vendor),
    db: Session = Depends(get_db),
):
    # Authorization and variants fetch
    allowed_variant_ids = validate_vendor_stay_and_get_variants(db, stay_property_id, current_user)
    
    # Get availability record
    availability = db.query(AvailabilityCalendar).filter(AvailabilityCalendar.id == availability_id).first()
    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability record not found")
        
    if availability.variant_id not in allowed_variant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Availability record does not belong to this stay property")
        
    # Check if reserved_capacity > 0
    if availability.reserved_capacity > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Cannot delete availability with active reservations (reservedCapacity = {availability.reserved_capacity})"
        )
        
    try:
        db.delete(availability)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete availability record") from exc
        
    return {"message": "Availability record deleted successfully", "availability_id": str(availability_id)}

