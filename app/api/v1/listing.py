from typing import List
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import math

from app.config.database import get_db
from app.repositories.listing_repo import ListingRepository
from app.schemas.listing_schema import (
    ListingCreate,
    ListingUpdate,
    ListingResponse,
    ListingListResponse,
    ListingSearchParams,
)
from app.models.enum import CurrencyCode, ListingType, ListingStatus

router = APIRouter()


def get_listing_repository(db: Session = Depends(get_db)) -> ListingRepository:
    """Dependency to get listing repository"""
    return ListingRepository(db)


@router.post("/", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_data: ListingCreate,
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Create a new listing"""
    
    # Check if listing with slug already exists
    if listing_data.slug and listing_repo.exists_by_slug(listing_data.slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing with this slug already exists"
        )
    
    try:
        listing = listing_repo.create(listing_data)
        return listing
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create listing"
        )


@router.get("/", response_model=ListingListResponse)
async def get_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get public listings with pagination."""

    page = skip // limit + 1
    search_params = ListingSearchParams(
        status=ListingStatus.PUBLISHED,
        is_active=True,
        page=page,
        per_page=limit,
    )
    listings, total = listing_repo.search(search_params)
    
    return ListingListResponse(
        listings=listings,
        total=total,
        page=skip // limit + 1,
        per_page=limit,
        total_pages=math.ceil(total / limit) if total > 0 else 0
    )


@router.get("/id/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: UUID,
    listing_repo: ListingRepository = Depends(get_listing_repository),
):
    """Get published public listing by ID"""

    listing = listing_repo.get_by_id(listing_id)
    if not listing or listing.status != ListingStatus.PUBLISHED or listing.is_active is not True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    return listing


@router.get("/search", response_model=ListingListResponse)
async def search_listings_get(
    listing_type: ListingType | None = Query(None),
    destination_id: UUID | None = Query(None),
    location: str | None = Query(None),
    title: str | None = Query(None),
    base_currency: CurrencyCode | None = Query(None),
    status: ListingStatus | None = Query(None),
    is_active: bool | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    adults: int | None = Query(None),
    children: int | None = Query(None),
    rooms: int | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Search listings with filters (GET)"""
    
    search_params = ListingSearchParams(
        listing_type=listing_type,
        destination_id=destination_id,
        location=location,
        title=title,
        base_currency=base_currency,
        status=ListingStatus.PUBLISHED,
        is_active=True,
        start_date=start_date,
        end_date=end_date,
        adults=adults,
        children=children,
        rooms=rooms,
        page=page,
        per_page=per_page
    )
    
    listings, total_count = listing_repo.search(search_params)
    
    return ListingListResponse(
        listings=listings,
        total=total_count,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total_count / per_page) if total_count > 0 else 0
    )


@router.post("/search", response_model=ListingListResponse)
async def search_listings(
    search_params: ListingSearchParams,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Search public listings with filters (POST)"""

    search_params.status = ListingStatus.PUBLISHED
    search_params.is_active = True
    listings, total_count = listing_repo.search(search_params)
    
    return ListingListResponse(
        listings=listings,
        total=total_count,
        page=search_params.page,
        per_page=search_params.per_page,
        total_pages=math.ceil(total_count / search_params.per_page) if total_count > 0 else 0
    )


@router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: UUID,
    listing_data: ListingUpdate,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Update listing by ID"""
    
    # Check if listing exists
    existing_listing = listing_repo.get_by_id(listing_id)
    if not existing_listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    # Check if slug is being updated and already exists
    if listing_data.slug and listing_repo.exists_by_slug(listing_data.slug, exclude_listing_id=listing_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing with this slug already exists"
        )
    
    try:
        updated_listing = listing_repo.update(listing_id, listing_data)
        return updated_listing
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update listing"
        )


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Delete listing by ID (hard delete)"""
    
    success = listing_repo.delete(listing_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )


@router.patch("/{listing_id}/archive", response_model=ListingResponse)
async def archive_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Archive listing (soft delete)"""
    
    listing = listing_repo.deactivate(listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    return listing


@router.patch("/{listing_id}/publish", response_model=ListingResponse)
async def publish_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Publish (activate) listing"""
    
    listing = listing_repo.activate(listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    return listing


@router.patch("/{listing_id}/draft", response_model=ListingResponse)
async def draft_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Set listing to draft (deactivate)"""
    
    listing = listing_repo.deactivate(listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    return listing


@router.get("/type/{listing_type}", response_model=List[ListingResponse])
async def get_listings_by_type(
    listing_type: ListingType,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get all listings by type"""
    
    listings = listing_repo.get_by_type(listing_type)
    return listings


@router.get("/active", response_model=List[ListingResponse])
async def get_active_listings(
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get all active listings"""
    
    listings = listing_repo.get_active()
    return listings


@router.get("/inactive", response_model=List[ListingResponse])
async def get_inactive_listings(
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get all inactive listings"""
    
    listings = listing_repo.get_inactive()
    return listings


@router.get("/city/{city}", response_model=List[ListingResponse])
async def get_listings_by_city(
    city: str,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get all listings by city"""
    
    listings = listing_repo.get_by_location_city(city)
    return listings


@router.get("/district/{district}", response_model=List[ListingResponse])
async def get_listings_by_district(
    district: str,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get all listings by district"""
    
    listings = listing_repo.get_by_location_district(district)
    return listings


@router.get("/currency/{currency}", response_model=List[ListingResponse])
async def get_listings_by_currency(
    currency: CurrencyCode,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get all listings by currency"""
    
    listings = listing_repo.get_by_currency(currency)
    return listings


@router.get("/location/search", response_model=List[ListingResponse])
async def search_listings_by_location(
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate"),
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in kilometers"),
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Search listings by geographic proximity"""
    
    listings = listing_repo.search_by_location(latitude, longitude, radius_km)
    return listings


@router.get("/stats/overview")
async def get_listing_stats(
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get listing count statistics"""
    
    type_counts = listing_repo.count_by_type()
    currency_counts = listing_repo.count_by_currency()
    
    active_count = listing_repo.count_active()
    inactive_count = listing_repo.count_inactive()
    
    return {
        "type_distribution": type_counts,
        "currency_distribution": currency_counts,
        "active_listings": active_count,
        "inactive_listings": inactive_count,
        "total_listings": active_count + inactive_count
    }


@router.get("/slug/{slug}", response_model=ListingResponse)
async def get_listing_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get listing by slug"""

    listing = listing_repo.get_by_slug(slug)
    if not listing or listing.status != ListingStatus.PUBLISHED or listing.is_active is not True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    return listing


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
    listing_repo: ListingRepository = Depends(get_listing_repository)
):
    """Get published public listing by ID"""

    listing = listing_repo.get_by_id(listing_id)
    if not listing or listing.status != ListingStatus.PUBLISHED or listing.is_active is not True:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    return listing
