from fastapi import APIRouter

from app.api.v1 import (
    admin,
    packages,
    users,
    listing,
    bookings,
    wishlist,
)

api_router = APIRouter()

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
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
    wishlist.router,
    prefix="/wishlist",
    tags=["wishlist"]
)
