from fastapi import APIRouter

from app.api.v1 import users, listing, bookings

api_router = APIRouter()

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