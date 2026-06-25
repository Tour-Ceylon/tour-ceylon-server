from fastapi import APIRouter

from app.api.v1.admin import addons, destinations, listings, packages, reset, settings, snapshot, stays, transport

router = APIRouter()
router.include_router(snapshot.router)
router.include_router(packages.router)
router.include_router(addons.router)
router.include_router(destinations.router)
router.include_router(listings.router)
router.include_router(transport.router)
router.include_router(stays.router)
router.include_router(settings.router)
router.include_router(reset.router)
