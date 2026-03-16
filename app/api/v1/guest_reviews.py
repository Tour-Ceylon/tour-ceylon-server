from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.repositories.guest_review_repo import GuestReviewRepository
from app.schemas.guest_review_schema import GuestReviewCreate, GuestReviewResponse

router = APIRouter()


def get_guest_review_repository(db: Session = Depends(get_db)) -> GuestReviewRepository:
    """Dependency to get guest review repository"""
    return GuestReviewRepository(db)


@router.post("/", response_model=GuestReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_review(
    review_data: GuestReviewCreate,
    review_repo: GuestReviewRepository = Depends(get_guest_review_repository)
):
    """Create a new guest review"""
    try:
        review = review_repo.create(review_data)
        return review
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create guest review"
        )


@router.get("/listing/{listing_id}", response_model=List[GuestReviewResponse])
async def get_guest_reviews_by_listing(
    listing_id: UUID,
    review_repo: GuestReviewRepository = Depends(get_guest_review_repository)
):
    """Get all guest reviews for a specific listing"""
    reviews = review_repo.get_by_listing(listing_id)
    return reviews