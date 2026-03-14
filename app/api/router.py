from fastapi import APIRouter

from app.api.v1 import users
from app.api.v1 import listing

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