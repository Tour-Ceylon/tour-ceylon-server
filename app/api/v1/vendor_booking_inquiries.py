import math
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.enum import UserRole
from app.models.listing import Listing
from app.models.stay import StayProperty
from app.models.bookingInquiry import BookingInquiry

logger = logging.getLogger("app.vendor_booking_inquiries")

router = APIRouter()


class StatusUpdatePayload(BaseModel):
    status: str


def is_admin_user(user: User) -> bool:
    role_val = getattr(user.role, "value", user.role)
    return str(role_val).lower() in ("admin", "superadmin")


@router.get("/", response_model=Dict[str, Any])
def list_vendor_booking_inquiries(
    status_filter: Optional[str] = Query(None, alias="status_filter"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch booking inquiries filtered specifically for the currently logged-in vendor.
    Superadmins receive all booking inquiries across the system.
    """
    logger.info(f"Fetching vendor booking inquiries for user={current_user.id} role={current_user.role}")

    is_admin = is_admin_user(current_user)

    if not is_admin:
        # Collect all listing IDs and property IDs belonging to this vendor
        v_listings = db.query(Listing).filter(Listing.vendor_id == current_user.id).all()
        v_props = db.query(StayProperty).filter(StayProperty.vendor_id == current_user.id).all()

        vendor_target_ids = set(str(l.id) for l in v_listings)
        vendor_target_ids.update(str(p.id) for p in v_props)
        vendor_target_ids.update(str(p.listing_id) for p in v_props if p.listing_id)
    else:
        vendor_target_ids = None

    # Fetch all inquiries (or filter base in DB)
    query = db.query(BookingInquiry)
    
    if status_filter and status_filter.lower() != "all":
        # Map frontend status filter to DB InquiryStatus
        db_status = status_filter.lower()
        if db_status == "pending":
            query = query.filter(BookingInquiry.status.in_(["pending_contact", "new", "contacted"]))
        elif db_status == "confirmed":
            query = query.filter(BookingInquiry.status == "quoted")
        elif db_status == "completed":
            query = query.filter(BookingInquiry.status == "converted_to_booking")
        elif db_status == "cancelled":
            query = query.filter(BookingInquiry.status == "cancelled")
        else:
            query = query.filter(BookingInquiry.status == db_status)

    all_inquiries = query.order_by(BookingInquiry.created_at.desc()).all()

    filtered_items = []
    status_counts = {
        "pending_contact": 0,
        "contacted": 0,
        "quoted": 0,
        "converted_to_booking": 0,
        "cancelled": 0
    }

    for inq in all_inquiries:
        cart_items = inq.cart_items or []
        
        if not is_admin and vendor_target_ids is not None:
            # Filter cart items to only those belonging to this vendor
            matching_items = []
            for item in cart_items:
                lid = item.get("listing_id") or item.get("listingId")
                if lid and str(lid) in vendor_target_ids:
                    matching_items.append(item)
            
            if not matching_items:
                continue
            visible_cart_items = matching_items
        else:
            visible_cart_items = cart_items

        # Apply text search filter if provided
        if search:
            s = search.lower()
            customer_name = f"{inq.first_name} {inq.last_name}".lower()
            ref = (inq.reference or "").lower()
            titles = " ".join(item.get("title", "").lower() for item in visible_cart_items)
            if s not in customer_name and s not in ref and s not in titles:
                continue

        # Count status
        st_val = getattr(inq.status, "value", str(inq.status)).lower()
        if st_val in status_counts:
            status_counts[st_val] += 1

        formatted_items = []
        for item in visible_cart_items:
            tdate_raw = item.get("travel_date_raw") or item.get("travelDateRaw")
            tdate = item.get("travel_date") or item.get("travelDate")
            tdate_end = item.get("travel_date_end") or item.get("travelDateEnd")

            display_date = tdate_raw
            if not display_date:
                if tdate and tdate_end:
                    display_date = f"{str(tdate)[:10]} to {str(tdate_end)[:10]}"
                else:
                    display_date = tdate

            formatted_items.append({
                "listingId": str(item.get("listing_id") or item.get("listingId") or ""),
                "title": item.get("title") or "Service Listing",
                "travelDate": display_date,
                "travelDateEnd": str(tdate_end) if tdate_end else None,
                "travelDateRaw": display_date,
                "travelCount": item.get("travel_count") or item.get("travelCount") or 1,
                "price": float(item.get("price") or 0.0),
                "baseCurrency": item.get("base_currency") or item.get("baseCurrency") or "USD"
            })

        filtered_items.append({
            "id": str(inq.id),
            "reference": inq.reference or f"INQ-{str(inq.id)[:8]}",
            "status": st_val,
            "firstName": inq.first_name,
            "lastName": inq.last_name,
            "email": inq.email,
            "phone": inq.phone or "",
            "nationality": inq.nationality or "",
            "emergencyContact": inq.emergency_contact,
            "numberOfTravelers": inq.number_of_travelers or 1,
            "specialRequests": inq.special_requests,
            "cartItems": formatted_items,
            "subtotal": float(inq.subtotal or 0.0),
            "total": float(inq.total or 0.0),
            "currency": str(inq.currency or "USD"),
            "createdAt": inq.created_at.isoformat() if inq.created_at else "",
            "updatedAt": inq.updated_at.isoformat() if inq.updated_at else ""
        })

    total_count = len(filtered_items)
    total_pages = max(1, math.ceil(total_count / per_page))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paged_items = filtered_items[start_idx:end_idx]

    return {
        "items": paged_items,
        "total": total_count,
        "page": page,
        "perPage": per_page,
        "totalPages": total_pages,
        "statusCounts": status_counts
    }


@router.patch("/{inquiry_id}/status", response_model=Dict[str, Any])
def update_vendor_inquiry_status(
    inquiry_id: UUID,
    payload: StatusUpdatePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a booking inquiry status as vendor, provision stay booking unit, and dispatch client confirmation email"""
    from app.services.booking_inquiry_service import BookingInquiryService
    from app.integrations.email_provider import EmailProvider

    inq = db.query(BookingInquiry).filter(BookingInquiry.id == inquiry_id).first()
    if not inq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking inquiry not found")

    new_status = payload.status.lower()
    inq.status = new_status
    db.commit()
    db.refresh(inq)

    st_val = getattr(inq.status, "value", str(inq.status)).lower()

    # Trigger room unit allocation and customer notification when vendor accepts/confirms booking
    if new_status in ("quoted", "converted_to_booking", "confirmed"):
        try:
            service = BookingInquiryService(db)
            service._auto_provision_stay_bookings(inq)
            detailed = service.get_inquiry_by_id(inq.id)
            if detailed:
                email_prov = EmailProvider()
                email_prov.send_vendor_booking_accepted_email(detailed)
                logger.info(f"Auto-provisioned room unit & dispatched confirmation email for inquiry {inq.reference}")
        except Exception as ex:
            logger.error(f"Error provisioning stay booking or sending email for inquiry {inq.reference}: {ex}")

    return {
        "id": str(inq.id),
        "reference": inq.reference,
        "status": st_val,
        "firstName": inq.first_name,
        "lastName": inq.last_name,
        "email": inq.email,
        "phone": inq.phone,
        "updatedAt": inq.updated_at.isoformat() if inq.updated_at else ""
    }
