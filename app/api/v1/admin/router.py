from fastapi import APIRouter

from app.api.v1.admin import addons, destinations, listings, packages, vendors, reset, settings, snapshot

router = APIRouter()
router.include_router(snapshot.router)
router.include_router(vendors.router)
router.include_router(packages.router)
router.include_router(addons.router)
router.include_router(destinations.router)
router.include_router(listings.router)
router.include_router(settings.router)
router.include_router(reset.router)
