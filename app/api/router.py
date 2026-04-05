from fastapi import APIRouter

from app.api.v1 import admin
from app.api.v1 import bookings
from app.api.v1 import users
from app.api.v1 import listing
<<<<<<< Updated upstream
=======
from app.api.v1 import packages
>>>>>>> Stashed changes

api_router = APIRouter()

# Include user routes
api_router.include_router(
    users.router,
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
    tags=["bookings"],
)

api_router.include_router(
<<<<<<< Updated upstream
    admin.router,
    prefix="/admin",
    tags=["admin"],
)
=======
    packages.router,
    prefix="/packages",
    tags=["packages"],
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
)
>>>>>>> Stashed changes
