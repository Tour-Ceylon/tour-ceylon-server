import logging
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.api.deps import get_current_user
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.user import User
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.listingBlock import ListingBlock
from app.schemas.safari_schema import (
    SafariBlockCreate,
    SafariBlockResponse,
    SafariBlockListResponse,
    SafariCalendarResponse,
    SafariVariantCalendar,
    SafariCalendarEntry
)

router = APIRouter()
logger = logging.getLogger("app.vendor_safaris")


def require_safari_vendor(current_user: User = Depends(get_current_user)) -> User:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    categories = current_user.approved_categories or ["Safari"]
    if role in {UserRole.ADMIN.value, "ADMIN", "admin"}:
        return current_user
    if role != UserRole.VENDOR.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only vendors or admins can manage safaris")
    if "Safari" not in categories:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor is not approved for Safari listings")
    return current_user


def ensure_safari_access(db: Session, current_user: User, listing_id: UUID) -> Listing:
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safari listing not found")
    
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role not in {UserRole.ADMIN.value, "ADMIN", "admin"}:
        if listing.vendor_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage this safari")
    return listing


@router.get("/{listing_id}/blocks", response_model=SafariBlockListResponse)
def get_safari_blocks(
    listing_id: UUID,
    start_date: date = Query(None, alias="startDate"),
    end_date: date = Query(None, alias="endDate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_safari_vendor)
):
    ensure_safari_access(db, current_user, listing_id)
    query = db.query(ListingBlock).filter(ListingBlock.listing_id == listing_id)
    if start_date:
        query = query.filter(ListingBlock.end_date >= start_date)
    if end_date:
        query = query.filter(ListingBlock.start_date <= end_date)
    blocks = query.all()
    return SafariBlockListResponse(blocks=blocks)


@router.post("/{listing_id}/blocks", status_code=status.HTTP_201_CREATED)
def create_safari_block(
    listing_id: UUID,
    payload: SafariBlockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_safari_vendor)
):
    ensure_safari_access(db, current_user, listing_id)
    
    # If no variants are provided, maybe block the whole listing?
    if not payload.variantIds:
        block = ListingBlock(
            listing_id=listing_id,
            variant_id=None,
            start_date=datetime.strptime(payload.startDate, "%Y-%m-%d").date(),
            end_date=datetime.strptime(payload.endDate, "%Y-%m-%d").date(),
            reason=payload.reason,
            block_type=payload.blockType
        )
        db.add(block)
        db.commit()
        return block

    created_blocks = []
    for var_id in payload.variantIds:
        block = ListingBlock(
            listing_id=listing_id,
            variant_id=UUID(var_id),
            start_date=datetime.strptime(payload.startDate, "%Y-%m-%d").date(),
            end_date=datetime.strptime(payload.endDate, "%Y-%m-%d").date(),
            reason=payload.reason,
            block_type=payload.blockType
        )
        db.add(block)
        created_blocks.append(block)
    
    db.commit()
    return {"message": "Blocks created", "count": len(created_blocks)}


@router.delete("/{listing_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def release_safari_block(
    listing_id: UUID,
    block_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_safari_vendor)
):
    ensure_safari_access(db, current_user, listing_id)
    block = db.query(ListingBlock).filter(ListingBlock.id == block_id, ListingBlock.listing_id == listing_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    db.delete(block)
    db.commit()
    return {"message": "Block released"}


@router.get("/{listing_id}/calendar", response_model=SafariCalendarResponse)
def get_safari_calendar(
    listing_id: UUID,
    start_date: date = Query(..., alias="startDate"),
    end_date: date = Query(..., alias="endDate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_safari_vendor)
):
    ensure_safari_access(db, current_user, listing_id)
    
    variants = db.query(ListingVariant).filter(
        ListingVariant.listing_id == listing_id, 
        ListingVariant.deleted_at == None
    ).all()

    # For now, just return empty entries or block entries.
    entries = []
    for v in variants:
        entries.append(SafariVariantCalendar(
            id=v.id,
            name=v.name,
            entries=[]
        ))
    
    return SafariCalendarResponse(entries=entries)
