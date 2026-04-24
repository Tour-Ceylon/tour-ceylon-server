from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.review_metric_schema import ReviewMetricCreate


class ReviewMetricRepository:
    """Legacy repository retained for compatibility after review metric model removal."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, metric_data: ReviewMetricCreate):
        raise NotImplementedError("ReviewMetricRepository is deprecated; review metrics are no longer stored as a standalone model.")

    def get_by_listing(self, listing_id: UUID) -> list:
        return []
