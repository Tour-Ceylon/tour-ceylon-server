from fastapi import APIRouter

from app.api.v1 import (
    admin,
    users, 
    listing, 
    bookings, 
    guest_reviews, 
    review_metrics, 
    rooms
)

api_router = APIRouter()

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
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
