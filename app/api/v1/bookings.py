from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, BackgroundTasks
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
from app.api.deps import get_current_user, get_current_user_id, require_role
from app.models.booking import Booking
from app.models.bookingItem import BookingItem
from app.models.enum import BookingStatus, UserRole, ChangedByType
from app.models.listing import Listing
from app.models.stay import StayProperty
from app.models.user import User
from app.services.booking_service import BookingService, get_booking_service

router = APIRouter()


def get_booking_repository(db: Session = Depends(get_db)) -> BookingRepository:
    """Dependency to get booking repository"""
    return BookingRepository(db)


# ---------------------------------------------------------------------------
# Authorization helpers
#
# These live at module level on purpose: several handlers below bind a path or
# query parameter named `status`, which shadows the imported `fastapi.status`
# inside those function bodies. Raising from here keeps access to the real
# status constants.
# ---------------------------------------------------------------------------


def _is_admin(user: User) -> bool:
    role_val = getattr(user.role, "value", user.role)
    return str(role_val).strip().upper() == UserRole.ADMIN.value


def _is_vendor(user: User) -> bool:
    role_val = getattr(user.role, "value", user.role)
    return str(role_val).strip().upper() == UserRole.VENDOR.value


def _vendor_owned_listing_ids(db: Session, vendor_id: UUID) -> set[str]:
    """
    Listing ids this vendor owns, including ids reachable through their stay
    properties. Mirrors the ownership resolution in
    app/api/v1/vendor_booking_inquiries.py so vendor scoping stays consistent.
    """
    owned: set[str] = {
        str(row[0])
        for row in db.query(Listing.id).filter(Listing.vendor_id == vendor_id).all()
    }
    for prop_id, prop_listing_id in db.query(
        StayProperty.id, StayProperty.listing_id
    ).filter(StayProperty.vendor_id == vendor_id).all():
        owned.add(str(prop_id))
        if prop_listing_id:
            owned.add(str(prop_listing_id))
    return owned


def _vendor_owns_booking(db: Session, user: User, booking: Booking) -> bool:
    owned = _vendor_owned_listing_ids(db, user.id)
    if not owned:
        return False
    return any(
        str(item.listing_id) in owned for item in (booking.booking_items or [])
    )


def _load_booking_for_caller(
    booking_repo: BookingRepository,
    db: Session,
    booking_id: UUID,
    current_user: User,
    *,
    allow_vendor: bool = False,
    hide_existence: bool = False,
) -> Booking:
    """
    Load a booking the caller is allowed to touch, or raise.

    Access is granted to the booking owner, to any ADMIN, and - when
    `allow_vendor` is set - to a VENDOR who owns one of the booked listings.

    `hide_existence=True` answers an unauthorized caller with 404 instead of
    403 so read endpoints do not confirm that another user's booking id
    exists. Action endpoints use 403, where refusing the action matters more
    than concealing the id.
    """
    booking = booking_repo.get_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.user_id == current_user.id or _is_admin(current_user):
        return booking

    if (
        allow_vendor
        and _is_vendor(current_user)
        and _vendor_owns_booking(db, current_user, booking)
    ):
        return booking

    if hide_existence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to act on this booking",
    )


def _authorize_user_scope(path_user_id: UUID, current_user: User) -> None:
    """Allow callers to read their own data; admins may read anyone's."""
    if path_user_id == current_user.id or _is_admin(current_user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only access your own bookings",
    )


# BookingUpdate fields that only an ADMIN may change. Each carries financial or
# lifecycle authority that a booking owner must not hold over their own record:
#   payment_status - would let an owner mark their own booking paid, bypassing
#                    PATCH /{booking_id}/mark-paid
#   status         - would let an owner self-confirm or self-complete, bypassing
#                    PATCH /{booking_id}/confirm and /complete
#   total_amount   - would let an owner rewrite the amount owed
_ADMIN_ONLY_UPDATE_FIELDS = frozenset({"payment_status", "status", "total_amount"})


def _reject_admin_only_update_fields(
    booking_data: BookingUpdate, current_user: User
) -> None:
    """
    Refuse a non-admin PUT that tries to write an admin-only field.

    Uses `model_fields_set` so only fields actually present in the request
    body are considered - an omitted field is not an attempted write, which
    matches the exclude_unset semantics BookingRepository.update() relies on.
    Rejecting outright (rather than silently dropping the fields) keeps the
    caller from believing a change was applied when it was not.
    """
    if _is_admin(current_user):
        return

    attempted = sorted(_ADMIN_ONLY_UPDATE_FIELDS & booking_data.model_fields_set)
    if not attempted:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Only an administrator may change the following field(s): "
            + ", ".join(attempted)
            + ". Use PATCH /bookings/{booking_id}/mark-paid to record payment "
            "or PATCH /bookings/{booking_id}/cancel to cancel this booking."
        ),
    )


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
    background_tasks: BackgroundTasks,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    """
    Create a new booking with dual payment methods, server pricing, per-night
    availability locking and duplicate-submit protection (SRV-PRC-05).

    The owner is taken from the authenticated token; BookingCreate no longer
    accepts a user_id, so a caller cannot book on another user's behalf.
    """
    service = get_booking_service(db)
    if booking_data.booking_items:
        first_item = booking_data.booking_items[0]
        recent_cutoff = datetime.utcnow() - timedelta(seconds=15)
        existing = (
            db.query(Booking)
            .join(Booking.booking_items)
            .filter(
                Booking.user_id == current_user_id,
                Booking.created_at >= recent_cutoff,
                BookingItem.listing_id == first_item.listing_id,
            )
            .first()
        )
        if existing:
            return existing
    return service.create_booking(
        booking_data, current_user_id, background_tasks=background_tasks
    )


@router.patch("/{booking_id}/mark-paid", response_model=BookingResponse)
def mark_booking_as_paid(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.VENDOR])),
):
    """Mark a pending bank transfer booking as PAID / SUCCEEDED (admin, or the
    vendor of a booked listing - the vendor portal booking centre calls this;
    booking owners cannot mark their own booking paid) (SRV-PAY-01)"""
    _load_booking_for_caller(
        booking_repo, db, booking_id, current_user, allow_vendor=True
    )
    service = get_booking_service(db)
    return service.mark_as_paid(booking_id, changed_by_user_id=current_user.id)


@router.post("/{booking_id}/receipt", response_model=BookingResponse)
def submit_booking_receipt(
    booking_id: UUID,
    receipt_data: BookingReceiptCreate,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user),
):
    """Submit bank transfer receipt reference (booking owner or admin)"""
    _load_booking_for_caller(booking_repo, db, booking_id, current_user)
    service = get_booking_service(db)
    return service.submit_receipt(booking_id, receipt_data)


@router.get("/me", response_model=List[BookingResponse])
@router.get("/me/", response_model=List[BookingResponse])
async def get_my_bookings(
    current_user_id: UUID = Depends(get_current_user_id),
    booking_repo: BookingRepository = Depends(get_booking_repository),
):
    """
    Bookings belonging to the authenticated user.

    Preferred over /bookings/user/{user_id}: there is no caller-supplied id to
    check, so there is nothing to forge. Registered ahead of /{booking_id} so
    the literal "me" is not captured by that route.
    """
    return booking_repo.get_by_user_id(current_user_id)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user),
):
    """Get booking by ID (owner, admin, or the vendor of a booked listing)"""

    return _load_booking_for_caller(
        booking_repo,
        db,
        booking_id,
        current_user,
        allow_vendor=True,
        hide_existence=True,
    )


@router.get("/user/{user_id}", response_model=List[BookingResponse])
async def get_bookings_by_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user),
):
    """Get all bookings for a specific user (self or admin). Prefer
    GET /bookings/me."""

    _authorize_user_scope(user_id, current_user)
    bookings = booking_repo.get_by_user_id(user_id)
    return bookings


@router.get("/listing/{listing_id}")
async def get_bookings_by_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get all bookings and inquiries for a specific listing (admin only)"""
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
    booking_repo: BookingRepository = Depends(get_booking_repository),
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get all bookings with pagination (admin only)"""
    
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
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Search bookings with filters (admin only)"""
    
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
    current_user: User = Depends(get_current_user),
):
    """
    Update booking by ID (booking owner or admin).

    An owner may only change the non-privileged fields; payment_status,
    status and total_amount are admin-only and a non-admin attempt to set
    them is refused with 403.
    """

    _load_booking_for_caller(booking_repo, db, booking_id, current_user)
    _reject_admin_only_update_fields(booking_data, current_user)

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
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """
    Delete booking by ID (hard delete; ADMIN only).

    Owners deliberately cannot reach this: the delete cascades to booking
    items, travelers, payment transactions and status history, destroying
    the financial audit trail. Customers cancel via
    PATCH /bookings/{booking_id}/cancel instead.
    """

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
    current_user: User = Depends(get_current_user),
):
    """Update booking status (admin, the vendor of a booked listing, or the
    booking owner cancelling their own booking) (SRV-PRC-04)"""

    _load_booking_for_caller(
        booking_repo, db, booking_id, current_user, allow_vendor=True
    )

    if _is_admin(current_user):
        changed_by = ChangedByType.ADMIN
    elif _is_vendor(current_user):
        changed_by = ChangedByType.USER
    else:
        # Reaching here means the caller is the booking owner (the guard above
        # admits only owner, admin, or the listing's vendor).
        if status_update.status != BookingStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tourists may only cancel their own bookings"
            )
        changed_by = ChangedByType.USER

    booking = booking_repo.update_status(
        booking_id,
        status_update.status,
        changed_by_type=changed_by,
        changed_by_user_id=current_user.id
    )
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
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.VENDOR])),
):
    """Confirm booking (set status to CONFIRMED) (admin, or the vendor of a
    booked listing)"""

    _load_booking_for_caller(
        booking_repo, db, booking_id, current_user, allow_vendor=True
    )
    changed_by = ChangedByType.ADMIN if _is_admin(current_user) else ChangedByType.USER
    booking = booking_repo.update_status(
        booking_id,
        BookingStatus.CONFIRMED,
        changed_by_type=changed_by,
        changed_by_user_id=current_user.id
    )
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
    current_user: User = Depends(get_current_user),
):
    """Cancel booking (set status to CANCELLED) (booking owner or admin)"""

    _load_booking_for_caller(booking_repo, db, booking_id, current_user)
    changed_by = ChangedByType.ADMIN if _is_admin(current_user) else ChangedByType.USER
    booking = booking_repo.update_status(
        booking_id,
        BookingStatus.CANCELLED,
        changed_by_type=changed_by,
        changed_by_user_id=current_user.id
    )
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
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.VENDOR])),
):
    """Complete booking (set status to COMPLETED) (admin, or the vendor of a
    booked listing)"""

    _load_booking_for_caller(
        booking_repo, db, booking_id, current_user, allow_vendor=True
    )
    changed_by = ChangedByType.ADMIN if _is_admin(current_user) else ChangedByType.USER
    booking = booking_repo.update_status(
        booking_id,
        BookingStatus.COMPLETED,
        changed_by_type=changed_by,
        changed_by_user_id=current_user.id
    )
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
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get all bookings by status (admin only)"""
    
    bookings = booking_repo.get_by_status(status)
    return bookings


@router.get("/user/{user_id}/status/{status}", response_model=List[BookingResponse])
async def get_user_bookings_by_status(
    user_id: UUID,
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    current_user: User = Depends(get_current_user),
):
    """Get user bookings by status (self or admin)"""

    _authorize_user_scope(user_id, current_user)
    bookings = booking_repo.get_user_bookings_by_status(user_id, status)
    return bookings


@router.get("/listing/{listing_id}/status/{status}", response_model=List[BookingResponse])
async def get_listing_bookings_by_status(
    listing_id: UUID,
    status: BookingStatus,
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get listing bookings by status (admin only)"""
    
    bookings = booking_repo.get_listing_bookings_by_status(listing_id, status)
    return bookings


@router.get("/stats/summary", response_model=BookingSummary)
async def get_booking_stats(
    db: Session = Depends(get_db),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get booking statistics summary (admin only)"""
    
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
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get revenue statistics (admin only)"""
    
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
    current_user: User = Depends(get_current_user),
):
    """Get booking statistics for a specific user (self or admin)"""

    _authorize_user_scope(user_id, current_user)
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
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    """Get booking statistics for a specific listing (admin only)"""
    
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