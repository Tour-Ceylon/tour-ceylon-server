from fastapi import APIRouter

from app.api.v1 import (
    admin,
    users, 
    listing, 
    bookings, 
    activities, 
    guest_reviews, 
    includes, 
    review_metrics, 
    rooms, 
    transfers
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

# Include new entity routes
api_router.include_router(
    activities.router,
    prefix="/activities",
    tags=["activities"]
)

api_router.include_router(
    guest_reviews.router,
    prefix="/guest-reviews",
    tags=["guest-reviews"]
)

api_router.include_router(
    includes.router,
    prefix="/includes",
    tags=["includes"]
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
    transfers.router,
    prefix="/transfers",
    tags=["transfers"]
)
