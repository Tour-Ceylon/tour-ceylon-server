import math
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config.database import get_db
<<<<<<< Updated upstream
from app.api.deps import get_current_user_id
from app.repositories.booking_repo import BookingRepository
from app.schemas.booking_schema import (
    BookingCreateRequest,
    BookingCreate, 
    BookingUpdate, 
    BookingResponse, 
    BookingListResponse, 
=======
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.repositories.booking_repo import BookingRepository
from app.schemas.booking_schema import (
    BookingCreateRequest,
    BookingUpdate,
    BookingResponse,
    BookingListResponse,
>>>>>>> Stashed changes
    BookingSearchParams,
    BookingStatusUpdate,
    BookingSummary
)
from app.models.enum import BookingStatus

public_router = APIRouter(prefix="/bookings", tags=["bookings"])
admin_router = APIRouter(prefix="/bookings", tags=["bookings"], dependencies=[Depends(require_admin)])
router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)


def get_booking_repository(db: Session = Depends(get_db)) -> BookingRepository:
    """Dependency to get booking repository"""
    return BookingRepository(db)


@public_router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_data: BookingCreateRequest,
<<<<<<< Updated upstream
    current_user_id: UUID = Depends(get_current_user_id),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Create a new booking"""

    booking_for_create = BookingCreate(
        user_id=current_user_id,
        listing_id=booking_data.listing_id,
        travel_date=booking_data.travel_date,
        travel_count=booking_data.travel_count,
        unit_price_minor=booking_data.unit_price_minor,
        total_price_minor=booking_data.total_price_minor,
        status=booking_data.status,
    )
    
    # Check if booking already exists for the same user, listing and travel date
    if booking_repo.exists_booking(
        booking_for_create.user_id,
        booking_for_create.listing_id,
        booking_for_create.travel_date,
    ):
=======
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Create a new booking for the authenticated user."""

    if booking_repo.exists_booking(current_user.id, booking_data.listing_id, booking_data.travel_date):
>>>>>>> Stashed changes
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking already exists for this user, listing and travel date"
        )
    
    try:
<<<<<<< Updated upstream
        booking = booking_repo.create(booking_for_create)
=======
        booking = booking_repo.create(current_user.id, booking_data)
>>>>>>> Stashed changes
        return booking
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking"
        )


<<<<<<< Updated upstream
@router.get("/me", response_model=List[BookingResponse])
async def get_my_bookings(
    current_user_id: UUID = Depends(get_current_user_id),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    """Get all bookings for the authenticated user"""
    return booking_repo.get_by_user_id(current_user_id)


@router.get("/me/status/{status}", response_model=List[BookingResponse])
async def get_my_bookings_by_status(
    status: BookingStatus,
    current_user_id: UUID = Depends(get_current_user_id),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    """Get authenticated user bookings by status"""
    return booking_repo.get_user_bookings_by_status(current_user_id, status)


@router.get("/me/stats")
async def get_my_booking_stats(
    current_user_id: UUID = Depends(get_current_user_id),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    """Get booking statistics for the authenticated user"""
    total_bookings = booking_repo.count_by_user(current_user_id)
    total_spent = booking_repo.get_user_total_spent(current_user_id)
    confirmed_spent = booking_repo.get_user_total_spent(current_user_id, BookingStatus.CONFIRMED)
    completed_spent = booking_repo.get_user_total_spent(current_user_id, BookingStatus.COMPLETED)

    return {
        "user_id": current_user_id,
        "total_bookings": total_bookings,
        "total_spent_minor": total_spent,
        "confirmed_spent_minor": confirmed_spent,
        "completed_spent_minor": completed_spent,
    }


@router.get("/{booking_id}", response_model=BookingResponse)
=======
@public_router.get("/me", response_model=List[BookingResponse])
async def get_my_bookings(
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    return booking_repo.get_by_user_id(current_user.id)


@public_router.get("/me/{booking_id}", response_model=BookingResponse)
async def get_my_booking(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    booking = booking_repo.get_by_id(booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@admin_router.get("/{booking_id}", response_model=BookingResponse)
>>>>>>> Stashed changes
async def get_booking(
    booking_id: UUID,
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


@admin_router.get("/user/{user_id}", response_model=List[BookingResponse])
async def get_bookings_by_user(
    user_id: UUID,
<<<<<<< Updated upstream
    current_user_id: UUID = Depends(get_current_user_id),
=======
>>>>>>> Stashed changes
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings for a specific user"""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for requested user",
        )
    
    bookings = booking_repo.get_by_user_id(user_id)
    return bookings


@admin_router.get("/listing/{listing_id}", response_model=List[BookingResponse])
async def get_bookings_by_listing(
    listing_id: UUID,
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings for a specific listing"""
    
    bookings = booking_repo.get_by_listing_id(listing_id)
    return bookings


@admin_router.get("/", response_model=BookingListResponse)
async def get_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
<<<<<<< Updated upstream
    status: BookingStatus = Query(None),
    db: Session = Depends(get_db),
=======
    status: BookingStatus | None = Query(None),
>>>>>>> Stashed changes
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings with pagination"""
    
    bookings = booking_repo.get_all(skip=skip, limit=limit, status=status)
    total = len(bookings)  # This is approximate, could be improved with a dedicated count method
    
    return BookingListResponse(
        bookings=bookings,
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        total_pages=math.ceil(total / limit) if total > 0 else 0
    )


@admin_router.post("/search", response_model=BookingListResponse)
async def search_bookings(
    search_params: BookingSearchParams,
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


@admin_router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: UUID,
    booking_data: BookingUpdate,
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


@admin_router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(
    booking_id: UUID,
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Delete booking by ID (hard delete)"""
    
    success = booking_repo.delete(booking_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )


@admin_router.patch("/{booking_id}/status", response_model=BookingResponse)
async def update_booking_status(
    booking_id: UUID,
    status_update: BookingStatusUpdate,
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


@admin_router.patch("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: UUID,
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


@admin_router.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
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


@admin_router.patch("/{booking_id}/complete", response_model=BookingResponse)
async def complete_booking(
    booking_id: UUID,
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


@admin_router.get("/status/{status}", response_model=List[BookingResponse])
async def get_bookings_by_status(
    status: BookingStatus,
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get all bookings by status"""
    
    bookings = booking_repo.get_by_status(status)
    return bookings


@admin_router.get("/user/{user_id}/status/{status}", response_model=List[BookingResponse])
async def get_user_bookings_by_status(
    user_id: UUID,
    status: BookingStatus,
<<<<<<< Updated upstream
    current_user_id: UUID = Depends(get_current_user_id),
=======
>>>>>>> Stashed changes
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get user bookings by status"""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for requested user",
        )
    
    bookings = booking_repo.get_user_bookings_by_status(user_id, status)
    return bookings


@admin_router.get("/listing/{listing_id}/status/{status}", response_model=List[BookingResponse])
async def get_listing_bookings_by_status(
    listing_id: UUID,
    status: BookingStatus,
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get listing bookings by status"""
    
    bookings = booking_repo.get_listing_bookings_by_status(listing_id, status)
    return bookings


@admin_router.get("/stats/summary", response_model=BookingSummary)
async def get_booking_stats(
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking statistics summary"""
    
    status_counts = booking_repo.count_by_status()
    total_revenue = booking_repo.get_total_revenue()
    
    return BookingSummary(
        total_bookings=sum(status_counts.values()),
<<<<<<< Updated upstream
        pending_payment=status_counts.get(BookingStatus.PENDING_PAYMENT, 0),
=======
        pending=status_counts.get(BookingStatus.PENDING_PAYMENT, 0),
>>>>>>> Stashed changes
        confirmed=status_counts.get(BookingStatus.CONFIRMED, 0),
        cancelled=status_counts.get(BookingStatus.CANCELLED, 0),
        completed=status_counts.get(BookingStatus.COMPLETED, 0),
        total_revenue_minor=total_revenue
    )


@admin_router.get("/stats/revenue")
async def get_revenue_stats(
<<<<<<< Updated upstream
    status: BookingStatus = Query(None),
    db: Session = Depends(get_db),
=======
    status: BookingStatus | None = Query(None),
>>>>>>> Stashed changes
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get revenue statistics"""
    
    total_revenue = booking_repo.get_total_revenue(status)
    confirmed_revenue = booking_repo.get_total_revenue(BookingStatus.CONFIRMED)
    completed_revenue = booking_repo.get_total_revenue(BookingStatus.COMPLETED)
    
    return {
        "total_revenue_minor": total_revenue,
        "confirmed_revenue_minor": confirmed_revenue,
        "completed_revenue_minor": completed_revenue,
        "realized_revenue_minor": confirmed_revenue + completed_revenue
    }


@admin_router.get("/user/{user_id}/stats")
async def get_user_booking_stats(
    user_id: UUID,
<<<<<<< Updated upstream
    current_user_id: UUID = Depends(get_current_user_id),
=======
>>>>>>> Stashed changes
    booking_repo: BookingRepository = Depends(get_booking_repository)
):
    """Get booking statistics for a specific user"""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for requested user",
        )
    
    total_bookings = booking_repo.count_by_user(user_id)
    total_spent = booking_repo.get_user_total_spent(user_id)
    confirmed_spent = booking_repo.get_user_total_spent(user_id, BookingStatus.CONFIRMED)
    completed_spent = booking_repo.get_user_total_spent(user_id, BookingStatus.COMPLETED)
    
    return {
        "user_id": user_id,
        "total_bookings": total_bookings,
        "total_spent_minor": total_spent,
        "confirmed_spent_minor": confirmed_spent,
        "completed_spent_minor": completed_spent
    }


@admin_router.get("/listing/{listing_id}/stats")
async def get_listing_booking_stats(
    listing_id: UUID,
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
        "total_revenue_minor": total_revenue,
        "confirmed_revenue_minor": confirmed_revenue,
        "completed_revenue_minor": completed_revenue
    }