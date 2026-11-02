from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.listingAddOn import ListingAddOn
from app.schemas.addon_schema import AddOnOut

router = APIRouter()


@router.get("/listing/{listing_id}", response_model=List[AddOnOut])
async def get_addons_by_listing(listing_id: UUID, db: Session = Depends(get_db)):
    """Active add-ons for a listing (public: shown on the listing page).

    Admins create, edit and delete them under /admin/addons. The old POST and DELETE routes here
    wrote to a repository that was only a stub, so they never stored anything and were removed.
    """
    return (
        db.query(ListingAddOn)
        .filter(ListingAddOn.listing_id == listing_id, ListingAddOn.is_active.is_(True))
        .order_by(ListingAddOn.created_at)
        .all()
    )
