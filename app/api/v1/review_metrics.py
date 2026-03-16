from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.repositories.review_repo import ReviewMetricRepository
from app.schemas.review_metric_schema import ReviewMetricCreate, ReviewMetricResponse

router = APIRouter()


def get_review_metric_repository(db: Session = Depends(get_db)) -> ReviewMetricRepository:
    """Dependency to get review metric repository"""
    return ReviewMetricRepository(db)


@router.post("/", response_model=ReviewMetricResponse, status_code=status.HTTP_201_CREATED)
async def create_review_metric(
    metric_data: ReviewMetricCreate,
    metric_repo: ReviewMetricRepository = Depends(get_review_metric_repository)
):
    """Create a new review metric"""
    try:
        metric = metric_repo.create(metric_data)
        return metric
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create review metric"
        )


@router.get("/listing/{listing_id}", response_model=List[ReviewMetricResponse])
async def get_review_metrics_by_listing(
    listing_id: UUID,
    metric_repo: ReviewMetricRepository = Depends(get_review_metric_repository)
):
    """Get all review metrics for a specific listing"""
    metrics = metric_repo.get_by_listing(listing_id)
    return metrics