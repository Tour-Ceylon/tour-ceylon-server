from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.repositories.activity_repo import ActivityRepository
from app.schemas.activity_schema import ActivityCreate, ActivityResponse

router = APIRouter()


def get_activity_repository(db: Session = Depends(get_db)) -> ActivityRepository:
    """Dependency to get activity repository"""
    return ActivityRepository(db)


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    activity_data: ActivityCreate,
    activity_repo: ActivityRepository = Depends(get_activity_repository)
):
    """Create a new activity"""
    try:
        activity = activity_repo.create(activity_data)
        return activity
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create activity"
        )


@router.get("/listing/{listing_id}", response_model=ActivityResponse)
async def get_activity_by_listing(
    listing_id: UUID,
    activity_repo: ActivityRepository = Depends(get_activity_repository)
):
    """Get activity by listing ID"""
    activity = activity_repo.get_by_listing(listing_id)
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found for this listing"
        )
    return activity