from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.reviewMetric import ReviewMetric
from app.schemas.review_metric_schema import ReviewMetricCreate


class ReviewMetricRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, metric_data: ReviewMetricCreate):

        metric = ReviewMetric(**metric_data.model_dump())

        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)

        return metric

    def get_by_listing(self, listing_id: UUID) -> List[ReviewMetric]:

        return (
            self.db.query(ReviewMetric)
            .filter(ReviewMetric.listing_id == listing_id)
            .all()
        )