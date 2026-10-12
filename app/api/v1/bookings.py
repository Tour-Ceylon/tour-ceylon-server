from datetime import date
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import math

from app.config.database import get_db
from app.repositories.booking_repo import BookingRepository
from app.schemas.booking_schema import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingListResponse,
    BookingSearchParams,
    BookingStatusUpdate,
    BookingSummary,
    BookingReceiptCreate,
    ListingAvailabilityResponse,
)
from app.models.enum import BookingStatus
from app.services.booking_service import BookingService, get_booking_service

router = APIRouter()


def get_booking_repository(db: Session = Depends(get_db)) -> BookingRepository:
    """Dependency to get booking repository"""
    return BookingRepository(db)


@router.get("/availability", response_model=ListingAvailabilityResponse)
def get_listing_availability(
    listing_id: UUID = Query(..., alias="listingId"),
    start_date: date = Query(..., alias="startDate"),
    end_date: date = Query(..., alias="endDate"),
    db: Session = Depends(get_db),
):
    """Get per-night availability for a listing between start_date and end_date"""
    service = get_booking_service(db)
    # Check for expired bank transfer holds first
    service.release_expired_bank_transfer_holds()
    return service.get_listing_availability(listing_id, start_date, end_date)


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
):
    """Create a new booking with dual payment methods and per-night availability locking"""
    service = get_booking_service(db)
    return service.create_booking(booking_data)


@router.patch("/{booking_id}/mark-paid", response_model=BookingResponse)
def mark_booking_as_paid(
    booking_id: UUID,
    db: Session = Depends(get_db),
):
    """Mark a pending bank transfer booking as PAID / SUCCEEDED"""
    service = get_booking_service(db)
    return service.mark_as_paid(booking_id)


@router.post("/{booking_id}/receipt", response_model=BookingResponse)
def submit_booking_receipt(
    booking_id: UUID,
    receipt_data: BookingReceiptCreate,
    db: Session = Depends(get_db),
):
    """Submit bank transfer receipt reference"""
    service = get_booking_service(db)
    return service.submit_receipt(booking_id, receipt_data)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking by ID"""
    
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.get("/user/{user_id}", response_model=List[BookingResponse])
async def get_bookings_by_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings for a specific user"""
    
    bookings = booking_repo.get_by_user_id(user_id)
    return bookings


@router.get("/listing/{listing_id}")
async def get_bookings_by_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings and inquiries for a specific listing"""
    results = []

    # 1. Query relational bookings table
    try:
        bookings = booking_repo.get_by_listing_id(listing_id)
        for b in bookings:
            matching_items = [it for it in (b.booking_items or []) if it.listing_id == listing_id]
            first_item = matching_items[0] if matching_items else None
            title = (first_item.item_metadata or {}).get("title", "Reserved Item") if first_item else "Reserved Item"
            slot = (first_item.item_metadata or {}).get("time_slot", "Morning Drive") if first_item else "Morning Drive"
            passengers = int((first_item.item_metadata or {}).get("guests", 1)) if first_item else 1
            travel_date = first_item.check_in.strftime("%Y-%m-%d") if (first_item and first_item.check_in) else ""
            st_val = b.status.value.upper() if hasattr(b.status, "value") else str(b.status).upper()

            results.append({
                "id": str(b.id),
                "booking_id": str(b.id),
                "guestName": f"Customer {str(b.user_id)[:8]}",
                "guest_name": f"Customer {str(b.user_id)[:8]}",
                "email": "",
                "package": title,
                "date": travel_date,
                "travel_date": travel_date,
                "slot": slot,
                "passengers": passengers,
                "price": f"${float(b.total_amount):.2f} {b.currency.value if hasattr(b.currency, 'value') else b.currency}",
                "total_amount": float(b.total_amount),
                "paymentMethod": "Card / Online",
                "payment_method": "Card / Online",
                "status": st_val,
            })
    except Exception:
        pass

    # 2. Query booking_inquiries table (where client store checkouts are recorded)
    try:
        from app.models.bookingInquiry import BookingInquiry
        inquiries = db.query(BookingInquiry).order_by(BookingInquiry.created_at.desc()).all()
        target_str = str(listing_id).lower()

        for inq in inquiries:
            cart_items = inq.cart_items or []
            matching_cart = []
            for item in cart_items:
                lid = str(item.get("listing_id") or item.get("listingId") or "").lower()
                if lid == target_str:
                    matching_cart.append(item)

            if not matching_cart:
                continue

            first_item = matching_cart[0]
            travel_date = first_item.get("travel_date_raw") or first_item.get("travel_date") or ""
            if travel_date and "T" in str(travel_date):
                travel_date = str(travel_date).split("T")[0]

            st_raw = getattr(inq.status, "value", str(inq.status)).upper()
            if st_raw in ("QUOTED", "CONVERTED_TO_BOOKING", "CONFIRMED"):
                ui_status = "CONFIRMED"
            elif st_raw in ("CANCELLED", "REJECTED"):
                ui_status = "REJECTED"
            else:
                ui_status = "PENDING"

            payment_pref = "Credit / Debit Card" if "Credit" in str(inq.special_requests or "") else "Pay on Arrival"

            curr_str = inq.currency.value if hasattr(inq.currency, "value") else str(inq.currency or "USD")
            results.append({
                "id": inq.reference or str(inq.id),
                "booking_id": inq.reference or str(inq.id),
                "raw_id": str(inq.id),
                "guestName": f"{inq.first_name or ''} {inq.last_name or ''}".strip() or "Guest",
                "guest_name": f"{inq.first_name or ''} {inq.last_name or ''}".strip() or "Guest",
                "email": inq.email or "",
                "phone": inq.phone or "",
                "package": first_item.get("title") or "Safari Game Drive",
                "date": travel_date,
                "travel_date": travel_date,
                "slot": first_item.get("time_slot") or "Morning Drive",
                "passengers": inq.number_of_travelers or 1,
                "price": f"${float(inq.total or inq.subtotal or 0):.2f} {curr_str}",
                "total_amount": float(inq.total or inq.subtotal or 0),
                "paymentMethod": payment_pref,
                "payment_method": payment_pref,
                "status": ui_status,
            })
    except Exception:
        pass

    return results


@router.get("/", response_model=BookingListResponse)
async def get_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: BookingStatus | None = Query(None),
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings with pagination"""
    
    bookings = booking_repo.get_all(skip=skip, limit=limit, status=status)
    status_counts = booking_repo.count_by_status()
    total = status_counts.get(status, 0) if status else sum(status_counts.values())
    
    return BookingListResponse(
        bookings=bookings,
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        total_pages=math.ceil(total / limit) if total > 0 else 0
    )


@router.post("/search", response_model=BookingListResponse)
async def search_bookings(
    search_params: BookingSearchParams,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Search bookings with filters"""
    
    bookings, total_count = booking_repo.search(search_params)
    
    return BookingListResponse(
        bookings=bookings,
        total=total_count,
        page=search_params.page,
        per_page=search_params.per_page,
        total_pages=math.ceil(total_count / search_params.per_page) if total_count > 0 else 0
    )


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: UUID,
    booking_data: BookingUpdate,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Update booking by ID"""
    
    # Check if booking exists
    existing_booking = booking_repo.get_by_id(booking_id)
    if not existing_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    try:
        updated_booking = booking_repo.update(booking_id, booking_data)
        return updated_booking
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update booking"
        )


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Delete booking by ID (hard delete)"""
    
    success = booking_repo.delete(booking_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )


@router.patch("/{booking_id}/status", response_model=BookingResponse)
async def update_booking_status(
    booking_id: UUID,
    status_update: BookingStatusUpdate,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Update booking status"""
    
    booking = booking_repo.update_status(booking_id, status_update.status)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.patch("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Confirm booking (set status to CONFIRMED)"""
    
    booking = booking_repo.update_status(booking_id, BookingStatus.CONFIRMED)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Cancel booking (set status to CANCELLED)"""
    
    booking = booking_repo.update_status(booking_id, BookingStatus.CANCELLED)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.patch("/{booking_id}/complete", response_model=BookingResponse)
async def complete_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Complete booking (set status to COMPLETED)"""
    
    booking = booking_repo.update_status(booking_id, BookingStatus.COMPLETED)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.get("/status/{status}", response_model=List[BookingResponse])
async def get_bookings_by_status(
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings by status"""
    
    bookings = booking_repo.get_by_status(status)
    return bookings


@router.get("/user/{user_id}/status/{status}", response_model=List[BookingResponse])
async def get_user_bookings_by_status(
    user_id: UUID,
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get user bookings by status"""
    
    bookings = booking_repo.get_user_bookings_by_status(user_id, status)
    return bookings


@router.get("/listing/{listing_id}/status/{status}", response_model=List[BookingResponse])
async def get_listing_bookings_by_status(
    listing_id: UUID,
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get listing bookings by status"""
    
    bookings = booking_repo.get_listing_bookings_by_status(listing_id, status)
    return bookings


@router.get("/stats/summary", response_model=BookingSummary)
async def get_booking_stats(
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking statistics summary"""
    
    status_counts = booking_repo.count_by_status()
    total_revenue = booking_repo.get_total_revenue()
    
    return BookingSummary(
        total_bookings=sum(status_counts.values()),
        pending=status_counts.get(BookingStatus.PENDING, 0),
        confirmed=status_counts.get(BookingStatus.CONFIRMED, 0),
        cancelled=status_counts.get(BookingStatus.CANCELLED, 0),
        completed=status_counts.get(BookingStatus.COMPLETED, 0),
        total_revenue=total_revenue
    )


@router.get("/stats/revenue")
async def get_revenue_stats(
    status: BookingStatus | None = Query(None),
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get revenue statistics"""
    
    total_revenue = booking_repo.get_total_revenue(status)
    confirmed_revenue = booking_repo.get_total_revenue(BookingStatus.CONFIRMED)
    completed_revenue = booking_repo.get_total_revenue(BookingStatus.COMPLETED)
    
    return {
        "total_revenue": total_revenue,
        "confirmed_revenue": confirmed_revenue,
        "completed_revenue": completed_revenue,
        "realized_revenue": confirmed_revenue + completed_revenue
    }


@router.get("/user/{user_id}/stats")
async def get_user_booking_stats(
    user_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking statistics for a specific user"""
    
    total_bookings = booking_repo.count_by_user(user_id)
    total_spent = booking_repo.get_user_total_spent(user_id)
    confirmed_spent = booking_repo.get_user_total_spent(user_id, BookingStatus.CONFIRMED)
    completed_spent = booking_repo.get_user_total_spent(user_id, BookingStatus.COMPLETED)
    
    return {
        "user_id": user_id,
        "total_bookings": total_bookings,
        "total_spent": total_spent,
        "confirmed_spent": confirmed_spent,
        "completed_spent": completed_spent
    }


@router.get("/listing/{listing_id}/stats")
async def get_listing_booking_stats(
    listing_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking statistics for a specific listing"""
    
    total_bookings = booking_repo.count_by_listing(listing_id)
    total_revenue = booking_repo.get_listing_total_revenue(listing_id)
    confirmed_revenue = booking_repo.get_listing_total_revenue(listing_id, BookingStatus.CONFIRMED)
    completed_revenue = booking_repo.get_listing_total_revenue(listing_id, BookingStatus.COMPLETED)
    
    return {
        "listing_id": listing_id,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "confirmed_revenue": confirmed_revenue,
        "completed_revenue": completed_revenue
    }
