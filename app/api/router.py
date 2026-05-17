from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    packages,
    users,
    listing,
    bookings,
    booking_inquiries,
    wishlist,
    guest_reviews,
    review_metrics,
    rooms,
    includes,
    transport
)

api_router = APIRouter()

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

api_router.include_router(
    packages.router,
    prefix="/packages",
    tags=["packages"]
)

# Include user routes
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    listing.router,
    prefix="/listings",
    tags=["listings"]
)

api_router.include_router(
    bookings.router,
    prefix="/bookings",
    tags=["bookings"]
)

api_router.include_router(
    booking_inquiries.router,
    prefix="/booking-inquiries",
    tags=["booking-inquiries"]
)

api_router.include_router(
    wishlist.router,
    prefix="/wishlist",
    tags=["wishlist"]
)

api_router.include_router(
    guest_reviews.router,
    prefix="/guest-reviews",
    tags=["guest-reviews"]
)

api_router.include_router(
    review_metrics.router,
    prefix="/review-metrics",
    tags=["review-metrics"]
)

api_router.include_router(
    rooms.router,
    prefix="/rooms",
    tags=["rooms"]
)

api_router.include_router(
    includes.router,
    prefix="/listing-addons",
    tags=["listing-addons"]
)

api_router.include_router(
    transport.router,
    prefix="/transport",
    tags=["transport"]
)
