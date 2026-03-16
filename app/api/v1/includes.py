from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.repositories.include_repo import ListingIncludeRepository
from app.schemas.include_schema import ListingIncludeCreate, ListingIncludeResponse

router = APIRouter()


def get_include_repository(db: Session = Depends(get_db)) -> ListingIncludeRepository:
    """Dependency to get listing include repository"""
    return ListingIncludeRepository(db)


@router.post("/", response_model=ListingIncludeResponse, status_code=status.HTTP_201_CREATED)
async def create_listing_include(
    include_data: ListingIncludeCreate,
    include_repo: ListingIncludeRepository = Depends(get_include_repository)
):
    """Create a new listing include"""
    try:
        include = include_repo.create(include_data)
        return include
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create listing include"
        )


@router.get("/listing/{listing_id}", response_model=List[ListingIncludeResponse])
async def get_includes_by_listing(
    listing_id: UUID,
    include_repo: ListingIncludeRepository = Depends(get_include_repository)
):
    """Get all includes for a specific listing"""
    includes = include_repo.get_by_listing(listing_id)
    return includes


@router.delete("/listing/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_includes_by_listing(
    listing_id: UUID,
    include_repo: ListingIncludeRepository = Depends(get_include_repository)
):
    """Delete all includes for a specific listing"""
    try:
        include_repo.delete_by_listing(listing_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete listing includes"
        )