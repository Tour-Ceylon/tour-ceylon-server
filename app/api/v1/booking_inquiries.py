from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.logging import logger
from app.models.enum import InquiryStatus, UserRole
from app.models.user import User
from app.schemas.booking_inquiry_schema import (
    BookingInquiryCreate,
    BookingInquiryResponse,
    BookingInquiryDetailed,
    BookingInquiryListResponse,
    BookingInquirySearchParams,
    BookingInquiryUpdate,
    AdminBookingInquiryItem,
    AdminBookingInquiryPaginatedResponse,
    VendorBookingInquiryPaginatedResponse,
    UpdateInquiryStatusPayload,
)
from app.services.booking_inquiry_service import get_booking_inquiry_service
from app.integrations.email_provider import email_provider

router = APIRouter()

# Separate routers for admin and vendor to avoid static/dynamic route conflicts
admin_router = APIRouter()
vendor_router = APIRouter()


def send_inquiry_notification_email(inquiry: BookingInquiryDetailed):
    """Background task to send booking inquiry notification email to business team"""
    try:
        success = email_provider.send_booking_inquiry_notification(inquiry)
        if success:
            logger.info(f"Business notification email sent for {inquiry.reference}")
        else:
            logger.error(f"Failed to send business notification email for {inquiry.reference}")
    except Exception as e:
        logger.error(f"Error sending business notification email: {str(e)}")


def send_customer_confirmation_email(inquiry: BookingInquiryDetailed):
    """Background task to send booking inquiry confirmation email to customer"""
    try:
        success = email_provider.send_booking_inquiry_customer_confirmation(inquiry)
        if success:
            logger.info(f"Customer confirmation email sent for {inquiry.reference} to {inquiry.email}")
        else:
            logger.error(f"Failed to send customer confirmation email for {inquiry.reference}")
    except Exception as e:
        logger.error(f"Error sending customer confirmation email: {str(e)}")


@router.post("/", response_model=BookingInquiryResponse, status_code=status.HTTP_201_CREATED)
async def create_booking_inquiry(
    request: Request,
    inquiry_data: BookingInquiryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new booking inquiry.
    
    This endpoint:
    1. Validates the booking inquiry payload
    2. Generates a unique inquiry reference (INQ-XXXXXXXX)
    3. Saves inquiry to database with status "pending_contact"
    4. Sends business notification email to admin team
    5. Sends confirmation email to customer
    6. Returns inquiry confirmation response
    """
    try:
        # Log the incoming request for debugging
        body = await request.body()
        logger.info(f"Received booking inquiry request body: {body.decode('utf-8')}")
        
        service = get_booking_inquiry_service(db)
        
        # Create the inquiry
        inquiry_response = service.create_inquiry(inquiry_data)
        
        # Get detailed inquiry for email notifications
        detailed_inquiry = service.get_inquiry_by_id(inquiry_response.id)
        if detailed_inquiry:
            # Add background tasks to send both emails
            background_tasks.add_task(send_inquiry_notification_email, detailed_inquiry)  # Business team
            background_tasks.add_task(send_customer_confirmation_email, detailed_inquiry)  # Customer
        
        logger.info(f"Booking inquiry created successfully: {inquiry_response.reference}")
        
        return inquiry_response
        
    except ValidationError as e:
        logger.warning(f"Pydantic validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Validation error",
                "errors": e.errors()
            }
        )
    except ValueError as e:
        logger.warning(f"Business validation error creating booking inquiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating booking inquiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking inquiry"
        )


@router.get("/{inquiry_id}", response_model=BookingInquiryDetailed)
def get_booking_inquiry(
    inquiry_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a booking inquiry by ID"""
    try:
        service = get_booking_inquiry_service(db)
        inquiry = service.get_inquiry_by_id(inquiry_id)
        
        if not inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found"
            )
        
        return inquiry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving booking inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve booking inquiry"
        )


@router.get("/reference/{reference}", response_model=BookingInquiryDetailed)
def get_booking_inquiry_by_reference(
    reference: str,
    db: Session = Depends(get_db)
):
    """Get a booking inquiry by reference number"""
    try:
        service = get_booking_inquiry_service(db)
        inquiry = service.get_inquiry_by_reference(reference)
        
        if not inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found"
            )
        
        return inquiry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving booking inquiry by reference {reference}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve booking inquiry"
        )


@router.get("/", response_model=BookingInquiryListResponse)
def search_booking_inquiries(
    email: str = None,
    status: InquiryStatus = None,
    nationality: str = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    """Search booking inquiries with optional filters"""
    try:
        service = get_booking_inquiry_service(db)
        
        search_params = BookingInquirySearchParams(
            email=email,
            status=status,
            nationality=nationality,
            page=page,
            per_page=per_page
        )
        
        result = service.search_inquiries(search_params)
        return result
        
    except Exception as e:
        logger.error(f"Error searching booking inquiries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search booking inquiries"
        )


@router.get("/email/{email}", response_model=List[BookingInquiryDetailed])
def get_inquiries_by_email(
    email: str,
    db: Session = Depends(get_db)
):
    """Get all booking inquiries for a specific email address"""
    try:
        service = get_booking_inquiry_service(db)
        inquiries = service.get_inquiries_by_email(email)
        return inquiries
        
    except Exception as e:
        logger.error(f"Error retrieving inquiries for email {email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiries"
        )


@router.put("/{inquiry_id}", response_model=BookingInquiryDetailed)
def update_booking_inquiry(
    inquiry_id: UUID,
    inquiry_data: BookingInquiryUpdate,
    db: Session = Depends(get_db)
):
    """Update a booking inquiry"""
    try:
        service = get_booking_inquiry_service(db)
        inquiry = service.update_inquiry(inquiry_id, inquiry_data)
        
        if not inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found"
            )
        
        return inquiry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating booking inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update booking inquiry"
        )


@router.patch("/{inquiry_id}/status", response_model=BookingInquiryDetailed)
def update_inquiry_status(
    inquiry_id: UUID,
    status: InquiryStatus,
    db: Session = Depends(get_db)
):
    """Update booking inquiry status"""
    try:
        service = get_booking_inquiry_service(db)
        inquiry = service.update_inquiry_status(inquiry_id, status)
        
        if not inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found"
            )
        
        return inquiry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inquiry status {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inquiry status"
        )


@router.delete("/{inquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking_inquiry(
    inquiry_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a booking inquiry"""
    try:
        service = get_booking_inquiry_service(db)
        success = service.delete_inquiry(inquiry_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting booking inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete booking inquiry"
        )


@router.get("/status/{status}", response_model=List[BookingInquiryDetailed])
def get_inquiries_by_status(
    status: InquiryStatus,
    db: Session = Depends(get_db)
):
    """Get all booking inquiries with specific status"""
    try:
        service = get_booking_inquiry_service(db)
        inquiries = service.get_inquiries_by_status(status)
        return inquiries
        
    except Exception as e:
        logger.error(f"Error retrieving inquiries by status {status}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiries"
        )


@router.get("/admin/statistics")
def get_inquiry_statistics(db: Session = Depends(get_db)):
    """Get booking inquiry statistics (admin endpoint)"""
    try:
        service = get_booking_inquiry_service(db)
        stats = service.get_inquiry_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving inquiry statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


# ---------------------------------------------------------------------------
# Admin router – requires ADMIN or SUPPORT role
# ---------------------------------------------------------------------------

@admin_router.get(
    "/",
    response_model=AdminBookingInquiryPaginatedResponse,
    summary="List all booking inquiries (admin)",
)
def admin_list_booking_inquiries(
    status_filter: Optional[InquiryStatus] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPPORT])),
):
    """
    Authenticated endpoint for admin/support to list all booking inquiries
    with pagination, status filters, search, date range, status counts and metrics.
    """
    try:
        service = get_booking_inquiry_service(db)
        result = service.list_admin_inquiries(
            status=status_filter,
            search=search,
            page=page,
            per_page=per_page,
            created_from=created_from,
            created_to=created_to,
        )
        return result
    except Exception as e:
        logger.error(f"Error listing admin booking inquiries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list booking inquiries",
        )


@admin_router.patch(
    "/{inquiry_id}/status",
    response_model=AdminBookingInquiryItem,
    summary="Update booking inquiry status (admin)",
)
def admin_update_inquiry_status(
    inquiry_id: UUID,
    payload: UpdateInquiryStatusPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPPORT])),
):
    """
    Admin/support endpoint to update a booking inquiry status.
    Allowed transitions: contacted, quoted, converted_to_booking, cancelled.

    TODO: trigger PDF/email confirmation after converted_to_booking.
    """
    try:
        service = get_booking_inquiry_service(db)
        db_inquiry = service.repository.get_by_id(inquiry_id)
        if not db_inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found",
            )

        updated = service.update_inquiry_status(inquiry_id, payload.status)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found",
            )

        logger.info(
            f"Admin {current_user.email} updated inquiry {inquiry_id} status to {payload.status}"
        )
        return service._convert_to_admin_item(service.repository.get_by_id(inquiry_id))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating admin inquiry status {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inquiry status",
        )


# ---------------------------------------------------------------------------
# Vendor router – requires VENDOR role (or ADMIN for testing)
# ---------------------------------------------------------------------------

def _require_vendor_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: allow VENDOR or ADMIN/SUPPORT to access vendor endpoints"""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    allowed = {UserRole.VENDOR.value, UserRole.ADMIN.value, UserRole.SUPPORT.value}
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only vendors or admins can access this endpoint",
        )
    return current_user


@vendor_router.get(
    "/",
    response_model=VendorBookingInquiryPaginatedResponse,
    summary="List vendor-owned booking inquiries",
)
def vendor_list_booking_inquiries(
    status_filter: Optional[InquiryStatus] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    vendor_id_override: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_vendor_or_admin),
):
    """
    Vendor endpoint to list only booking inquiries where at least one cart item
    listing belongs to the current vendor. Admins can pass vendor_id_override for testing.
    """
    try:
        role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        is_admin = role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}

        # Admins may pass a vendor_id_override for testing; vendors always use their own id
        effective_vendor_id = vendor_id_override if (is_admin and vendor_id_override) else current_user.id

        service = get_booking_inquiry_service(db)
        result = service.list_vendor_inquiries(
            vendor_id=effective_vendor_id,
            status=status_filter,
            search=search,
            page=page,
            per_page=per_page,
        )
        return result
    except Exception as e:
        logger.error(f"Error listing vendor booking inquiries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list vendor booking inquiries",
        )


@vendor_router.patch(
    "/{inquiry_id}/status",
    response_model=AdminBookingInquiryItem,
    summary="Update booking inquiry status (vendor – limited)",
)
def vendor_update_inquiry_status(
    inquiry_id: UUID,
    payload: UpdateInquiryStatusPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_vendor_or_admin),
):
    """
    Vendor endpoint to update a booking inquiry status.
    Vendors may only set: contacted, quoted.
    converted_to_booking and cancelled are admin-only.
    """
    VENDOR_ALLOWED_STATUSES = {InquiryStatus.CONTACTED, InquiryStatus.QUOTED}

    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    is_admin = role in {UserRole.ADMIN.value, UserRole.SUPPORT.value}

    if not is_admin and payload.status not in VENDOR_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vendors may only set status to: {', '.join(s.value for s in VENDOR_ALLOWED_STATUSES)}",
        )

    try:
        service = get_booking_inquiry_service(db)
        db_inquiry = service.repository.get_by_id(inquiry_id)
        if not db_inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found",
            )

        # Vendors may only update inquiries that contain their own listings
        if not is_admin:
            from app.models.listing import Listing
            vendor_listing_ids = {
                str(l_id)
                for (l_id,) in db.query(Listing.id).filter(Listing.vendor_id == current_user.id).all()
            }
            has_matching = any(
                (dict(item).get("listing_id") or dict(item).get("listingId")) in vendor_listing_ids
                for item in db_inquiry.cart_items
            )
            if not has_matching:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Inquiry does not belong to your listings",
                )

        service.update_inquiry_status(inquiry_id, payload.status)
        logger.info(
            f"Vendor {current_user.email} updated inquiry {inquiry_id} status to {payload.status}"
        )
        return service._convert_to_admin_item(service.repository.get_by_id(inquiry_id))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vendor inquiry status {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inquiry status",
        )