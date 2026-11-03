from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db, require_role
from app.core.logging import logger
from app.models.bookingInquiry import BookingInquiry
from app.models.enum import InquiryStatus, UserRole
from app.models.transportBooking import TransportBooking
from app.schemas.booking_inquiry_schema import (
    BookingInquiryPublicView,
    InquiryCancelRequest,
    QuoteRequestCreate,
    BookingInquiryCreate,
    BookingInquiryResponse,
    BookingInquiryDetailed,
    BookingInquiryListResponse,
    BookingInquirySearchParams,
    BookingInquiryUpdate
)
from app.services.booking_inquiry_service import get_booking_inquiry_service
from app.integrations.email_provider import email_provider
from app.api.v1.transport import (
    send_transport_notification_email,
    send_transport_customer_confirmation_email,
)

router = APIRouter()


def send_inquiry_notification_email(inquiry: BookingInquiryDetailed):
    """Background task to send booking inquiry notification email to business team"""
    try:
        success = email_provider.send_booking_inquiry_notification(inquiry)
        if success:
            logger.info(f"Business notification email sent for {inquiry.reference}")
        else:
            logger.error(f"Failed to send business notification email for {inquiry.reference}")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error sending business notification email: {str(e)}")


def send_customer_confirmation_email(inquiry: BookingInquiryDetailed):
    """Background task to send booking inquiry confirmation email to customer"""
    try:
        success = email_provider.send_booking_inquiry_customer_confirmation(inquiry)
        if success:
            logger.info(f"Customer confirmation email sent for {inquiry.reference}")
        else:
            logger.error(f"Failed to send customer confirmation email for {inquiry.reference}")
    except HTTPException:
        db.rollback()
        raise
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
        # SEC-4: never log the request body (it contains name, email, phone). Log counts only.
        body = await request.body()
        logger.info(
            "Received booking inquiry request: cart_items=%d bytes=%d",
            len(inquiry_data.cart_items),
            len(body),
        )
        
        # Preserve raw travel_date strings (e.g. "2026-09-16 to 2026-09-20") that
        # the Pydantic validator strips down to a single datetime.  The auto-provisioning
        # code for Stay bookings needs the full range to set correct check-out dates.
        try:
            import json as _json
            raw_body = _json.loads(body)
            raw_cart = raw_body.get("cartItems") or raw_body.get("cart_items") or []
            for idx, cart_item_schema in enumerate(inquiry_data.cart_items):
                if idx < len(raw_cart):
                    raw_td = raw_cart[idx].get("travelDate") or raw_cart[idx].get("travel_date") or ""
                    if isinstance(raw_td, str) and raw_td.strip():
                        cart_item_schema.travel_date_raw = raw_td.strip()
        except Exception as _ex:
            logger.warning(f"Could not inject travel_date_raw: {_ex}")
        
        service = get_booking_inquiry_service(db)
        
        # Create the inquiry
        inquiry_response = service.create_inquiry(inquiry_data)
        
        # Get detailed inquiry for email notifications
        detailed_inquiry = service.get_inquiry_by_id(inquiry_response.id)
        if detailed_inquiry:
            # Add background tasks to send both emails
            background_tasks.add_task(send_inquiry_notification_email, detailed_inquiry)  # Business team
            background_tasks.add_task(send_customer_confirmation_email, detailed_inquiry)  # Customer

        # Dispatch transport-specific emails for any auto-provisioned transport bookings
        for provisioned in getattr(service, "last_provisioned_transports", []):
            try:
                tb = (
                    db.query(TransportBooking)
                    .options(joinedload(TransportBooking.vehicle_category))
                    .filter(TransportBooking.id == provisioned.id)
                    .first()
                )
                if tb:
                    background_tasks.add_task(send_transport_notification_email, tb)
                    background_tasks.add_task(send_transport_customer_confirmation_email, tb)
                    logger.info("Queued transport emails for provisioned booking %s", tb.booking_reference)
            except Exception as t_err:
                logger.error("Failed to queue transport emails: %s", t_err)

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
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error creating booking inquiry: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking inquiry"
        )


@router.get("/me", response_model=List[BookingInquiryDetailed])
def list_my_booking_inquiries(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """FLOW-2: the signed-in customer's own inquiries, matched on their account email (newest first)."""
    service = get_booking_inquiry_service(db)
    return service.list_inquiries_for_email(current_user.email)


@router.post("/quote-request", response_model=BookingInquiryResponse, status_code=status.HTTP_201_CREATED)
def create_quote_request(
    data: QuoteRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """FLOW-4: a custom-quote request (no cart, no payment). The team follows up by email or phone."""
    service = get_booking_inquiry_service(db)
    response = service.create_quote_request(data)
    detailed = service.get_inquiry_by_id(response.id)
    if detailed:
        background_tasks.add_task(send_inquiry_notification_email, detailed)
        background_tasks.add_task(send_customer_confirmation_email, detailed)
    return response


@router.get("/{inquiry_id}", dependencies=[Depends(require_role([UserRole.ADMIN]))], response_model=BookingInquiryDetailed)
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
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error retrieving booking inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve booking inquiry"
        )


@router.get("/reference/{reference}", response_model=BookingInquiryPublicView, response_model_by_alias=True)
def get_booking_inquiry_by_reference(
    reference: str,
    db: Session = Depends(get_db)
):
    """FLOW-7: status and amounts for a reference (confirmation page, email links). No phone or email is returned."""
    service = get_booking_inquiry_service(db)
    view = service.get_public_view(reference.strip().upper())
    if not view:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking inquiry not found")
    return view


@router.post("/reference/{reference}/cancel", response_model=BookingInquiryPublicView, response_model_by_alias=True)
def cancel_booking_inquiry_by_reference(
    reference: str,
    body: InquiryCancelRequest,
    db: Session = Depends(get_db)
):
    """FLOW-6: the guest cancels their own request. The email used to book must match."""
    service = get_booking_inquiry_service(db)
    view = service.cancel_for_customer(reference.strip().upper(), body.email)
    if not view:
        # Same answer for "no such reference" and "wrong email" so references cannot be probed.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No request found for that reference and email")
    return view


@router.get("/", dependencies=[Depends(require_role([UserRole.ADMIN]))], response_model=BookingInquiryListResponse)
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
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error searching booking inquiries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search booking inquiries"
        )


@router.get("/email/{email}", dependencies=[Depends(require_role([UserRole.ADMIN]))], response_model=List[BookingInquiryDetailed])
def get_inquiries_by_email(
    email: str,
    db: Session = Depends(get_db)
):
    """Get all booking inquiries for a specific email address"""
    try:
        service = get_booking_inquiry_service(db)
        inquiries = service.get_inquiries_by_email(email)
        return inquiries
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error retrieving inquiries by email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiries"
        )


@router.put("/{inquiry_id}", dependencies=[Depends(require_role([UserRole.ADMIN]))], response_model=BookingInquiryDetailed)
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
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error updating booking inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update booking inquiry"
        )


class _StatusUpdateBody(BaseModel):
    status: InquiryStatus


@router.patch("/{inquiry_id}/status", response_model=BookingInquiryDetailed)
def update_inquiry_status(
    inquiry_id: UUID,
    body: _StatusUpdateBody,
    db: Session = Depends(get_db),
    _admin=Depends(require_role([UserRole.ADMIN])),
):
    """Update booking inquiry status (admin only; vendors use /vendor/booking-inquiries)"""
    try:
        service = get_booking_inquiry_service(db)
        approved = (InquiryStatus.QUOTED, InquiryStatus.CONVERTED_TO_BOOKING)
        existing = db.query(BookingInquiry).filter(BookingInquiry.id == inquiry_id).first()
        was_approved = existing is not None and existing.status in approved
        inquiry = service.update_inquiry_status(inquiry_id, body.status)
        
        if not inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking inquiry not found"
            )

        # The first time a request is approved the guest is emailed (a stay gets a pay link).
        if body.status in approved and not was_approved:
            try:
                from app.services.inquiry_approval import notify_inquiry_approved
                notify_inquiry_approved(db, db.query(BookingInquiry).filter(BookingInquiry.id == inquiry_id).first())
            except Exception as email_error:
                logger.error(f"Approval email failed for inquiry {inquiry_id}: {email_error}")
        
        return inquiry
        
    except HTTPException:
        raise
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error updating inquiry status {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inquiry status"
        )


@router.delete("/{inquiry_id}", dependencies=[Depends(require_role([UserRole.ADMIN]))], status_code=status.HTTP_204_NO_CONTENT)
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
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error deleting booking inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete booking inquiry"
        )


@router.get("/status/{status}", dependencies=[Depends(require_role([UserRole.ADMIN]))], response_model=List[BookingInquiryDetailed])
def get_inquiries_by_status(
    status: InquiryStatus,
    db: Session = Depends(get_db)
):
    """Get all booking inquiries with specific status"""
    try:
        service = get_booking_inquiry_service(db)
        inquiries = service.get_inquiries_by_status(status)
        return inquiries
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error retrieving inquiries by status {status}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiries"
        )


@router.get("/admin/statistics", dependencies=[Depends(require_role([UserRole.ADMIN]))])
def get_inquiry_statistics(db: Session = Depends(get_db)):
    """Get booking inquiry statistics (admin endpoint)"""
    try:
        service = get_booking_inquiry_service(db)
        stats = service.get_inquiry_statistics()
        return stats
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error retrieving inquiry statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )