"""FEAT-3: admin CRUD for listing add-ons (stored in `listing_addons`).

The previous version of this router called a repository that was never created, so every call
failed. The customer site reads the public list at GET /listing-addons/listing/{id}.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.listing import Listing
from app.models.listingAddOn import ListingAddOn
from app.schemas.addon_schema import AddOnCreate, AddOnOut, AddOnUpdate

router = APIRouter(
    prefix="/addons",
    tags=["admin-addons"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))],
)


def _get_or_404(db: Session, addon_id: UUID) -> ListingAddOn:
    addon = db.get(ListingAddOn, addon_id)
    if addon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Add-on not found")
    return addon


@router.get("", response_model=list[AddOnOut])
def list_addons(listing_id: UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(ListingAddOn)
    if listing_id:
        query = query.filter(ListingAddOn.listing_id == listing_id)
    return query.order_by(ListingAddOn.created_at.desc()).limit(500).all()


@router.post("", response_model=AddOnOut, status_code=status.HTTP_201_CREATED)
def create_addon(payload: AddOnCreate, db: Session = Depends(get_db)):
    if db.get(Listing, payload.listing_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    addon = ListingAddOn(**{**payload.model_dump(), "base_currency": payload.base_currency.upper()})
    db.add(addon)
    db.commit()
    db.refresh(addon)
    return addon


@router.patch("/{addon_id}", response_model=AddOnOut)
def update_addon(addon_id: UUID, payload: AddOnUpdate, db: Session = Depends(get_db)):
    addon = _get_or_404(db, addon_id)
    changes = payload.model_dump(exclude_unset=True)
    if "base_currency" in changes and changes["base_currency"]:
        changes["base_currency"] = changes["base_currency"].upper()
    for field, value in changes.items():
        setattr(addon, field, value)
    db.commit()
    db.refresh(addon)
    return addon


@router.delete("/{addon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_addon(addon_id: UUID, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, addon_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
