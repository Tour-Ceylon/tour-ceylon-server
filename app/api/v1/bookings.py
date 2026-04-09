from typing import List
from uuid import UUID
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import math

from app.config.database import get_db
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.user import User
from app.models.enum import UserRole
from app.repositories.booking_repo import BookingRepository
from app.schemas.booking_schema import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingListResponse,
    BookingSearchParams,
    BookingStatusUpdate,
    BookingSummary,
    BookingItemCreate,
    CheckoutBookingCreate,
    CheckoutBookingResponse,
)
from app.models.enum import BookingStatus, PaymentTransactionStatus
from app.api.deps import get_current_user

logger = logging.getLogger("app.bookings")

router = APIRouter()


def get_booking_repository(db: Session = Depends(get_db)) -> BookingRepository:
    """Dependency to get booking repository"""
    return BookingRepository(db)


def _get_checkout_variant(db: Session, listing_id: UUID) -> ListingVariant:
    variant = (
        db.query(ListingVariant)
        .filter(
            ListingVariant.listing_id == listing_id,
            ListingVariant.is_active.is_(True),
            ListingVariant.is_default.is_(True),
        )
        .first()
    )

    if variant is None:
        variant = (
            db.query(ListingVariant)
            .filter(
                ListingVariant.listing_id == listing_id,
                ListingVariant.is_active.is_(True),
            )
            .order_by(ListingVariant.created_at.asc())
            .first()
        )

    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This listing is not ready for checkout",
        )

    return variant


def _build_checkout_booking_payload(
    checkout_data: CheckoutBookingCreate,
    listing: Listing,
    variant: ListingVariant,
) -> BookingCreate:
    unit_price = Decimal(checkout_data.unit_price_minor) / Decimal("100")
    total_price = Decimal(checkout_data.total_price_minor) / Decimal("100")

    return BookingCreate(
        booking_reference=f"BK-{uuid4().hex[:12].upper()}",
        status=checkout_data.status,
        total_amount=total_price,
        currency=listing.base_currency,
        payment_status=PaymentTransactionStatus.PENDING,
        booked_at=datetime.now(timezone.utc),
        booking_items=[
            BookingItemCreate(
                listing_id=checkout_data.listing_id,
                variant_id=variant.id,
                travel_date=checkout_data.travel_date.date(),
                quantity=checkout_data.travel_count,
                unit_price=float(unit_price),
                total_price=float(total_price),
                travelers=[],
            )
        ],
    )


def _to_checkout_response(
    booking: BookingResponse | object,
    checkout_data: CheckoutBookingCreate,
) -> CheckoutBookingResponse:
    created_at = getattr(booking, "created_at")
    booking_id = getattr(booking, "id")
    user_id = getattr(booking, "user_id")
    status_value = getattr(booking, "status")

    return CheckoutBookingResponse(
        id=booking_id,
        user_id=user_id,
        listing_id=checkout_data.listing_id,
        travel_date=checkout_data.travel_date,
        travel_count=checkout_data.travel_count,
        unit_price_minor=checkout_data.unit_price_minor,
        total_price_minor=checkout_data.total_price_minor,
        status=status_value,
        created_at=created_at,
    )


@router.post("/checkout", response_model=CheckoutBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_checkout_booking(
    checkout_data: CheckoutBookingCreate,
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    """Create a checkout booking from the client-facing cart payload."""

    listing = booking_repo.db.query(Listing).filter(Listing.id == checkout_data.listing_id).first()
    if listing is None or not listing.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    if booking_repo.exists_booking(
        current_user.id,
        checkout_data.listing_id,
        checkout_data.travel_date.date(),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking already exists for this user, listing and travel date",
        )

    variant = _get_checkout_variant(booking_repo.db, checkout_data.listing_id)
    booking_payload = _build_checkout_booking_payload(checkout_data, listing, variant)

    try:
        booking = booking_repo.create(booking_payload, owner_user_id=current_user.id)
        return _to_checkout_response(booking, checkout_data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("checkout.booking_create_failed listing_id=%s", checkout_data.listing_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking",
        ) from exc


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_data: BookingCreate,
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Create a new booking. Owner is derived from authenticated user token."""
    
    first_booking_item = booking_data.booking_items[0]
    if booking_repo.exists_booking(
        current_user.id,
        first_booking_item.listing_id,
        first_booking_item.travel_date,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking already exists for this user, listing and travel date"
        )
    
    try:
        booking = booking_repo.create(booking_data, owner_user_id=current_user.id)
        return booking
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking"
        )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking by ID. Owner or admin only."""
    
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Enforce ownership: user must be owner or admin
    if booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this booking"
        )
    
    return booking


@router.get("/user/{user_id}", response_model=List[BookingResponse])
async def get_bookings_by_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings for a specific user. Self or admin only."""
    
    # Enforce: user can only list their own bookings unless admin
    if user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these bookings"
        )
    
    bookings = booking_repo.get_by_user_id(user_id)
    return bookings


@router.get("/listing/{listing_id}", response_model=List[BookingResponse])
async def get_bookings_by_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get all bookings for a specific listing (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized listing bookings access attempt by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view listing bookings")
    
    bookings = booking_repo.get_by_listing_id(listing_id)
    return bookings


@router.get("/", response_model=BookingListResponse)
async def get_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: BookingStatus | None = Query(None),
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get all bookings with pagination (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized bookings list access attempt by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view all bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Search bookings with filters (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking search attempt by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can search bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Update booking by ID (owner or admin only)"""
    
    # Check if booking exists
    existing_booking = booking_repo.get_by_id(booking_id)
    if not existing_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Authorization: owner or admin
    if existing_booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking update by user {current_user.id} for booking {booking_id}")
        raise HTTPException(status_code=403, detail="You can only update your own bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Delete booking by ID (owner or admin only)"""
    
    existing_booking = booking_repo.get_by_id(booking_id)
    if not existing_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Authorization: owner or admin
    if existing_booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking delete by user {current_user.id} for booking {booking_id}")
        raise HTTPException(status_code=403, detail="You can only delete your own bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Update booking status (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking status update by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can update booking status")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Confirm booking (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking confirm by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can confirm bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Cancel booking (owner or admin only)"""
    
    existing_booking = booking_repo.get_by_id(booking_id)
    if not existing_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Authorization: owner or admin
    if existing_booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking cancel by user {current_user.id} for booking {booking_id}")
        raise HTTPException(status_code=403, detail="You can only cancel your own bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Complete booking (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking completion by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can complete bookings")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get all bookings by status (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized bookings by status access by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view bookings by status")
    
    bookings = booking_repo.get_by_status(status)
    return bookings


@router.get("/user/{user_id}/status/{status}", response_model=List[BookingResponse])
async def get_user_bookings_by_status(
    user_id: UUID,
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get user bookings by status (owner or admin only)"""
    
    # Authorization: user viewing own bookings or admin
    if user_id != current_user.id and current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized user bookings by status access by user {current_user.id} for user {user_id}")
        raise HTTPException(status_code=403, detail="You can only view your own bookings")
    
    bookings = booking_repo.get_user_bookings_by_status(user_id, status)
    return bookings


@router.get("/listing/{listing_id}/status/{status}", response_model=List[BookingResponse])
async def get_listing_bookings_by_status(
    listing_id: UUID,
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get listing bookings by status (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized listing bookings by status access by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view listing bookings by status")
    
    bookings = booking_repo.get_listing_bookings_by_status(listing_id, status)
    return bookings


@router.get("/stats/summary", response_model=BookingSummary)
async def get_booking_stats(
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get booking statistics summary (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized booking stats access by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view booking statistics")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get revenue statistics (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized revenue stats access by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view revenue statistics")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get booking statistics for a specific user (owner or admin only)"""
    
    # Authorization: user viewing own stats or admin
    if user_id != current_user.id and current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized user stats access by user {current_user.id} for user {user_id}")
        raise HTTPException(status_code=403, detail="You can only view your own statistics")
    
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user)
):
    """Get booking statistics for a specific listing (admin only)"""
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized listing stats access by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Only admins can view listing statistics")
    
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
