from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.user import User
from app.api.v1.admin import addons, listings, packages, reset, settings, snapshot

router = APIRouter(dependencies=[Depends(require_admin)])
router.include_router(snapshot.router)
router.include_router(packages.router)
router.include_router(addons.router)
router.include_router(listings.router)
router.include_router(settings.router)
router.include_router(reset.router)

