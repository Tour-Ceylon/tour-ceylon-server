from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.guestReview import GuestReview
from app.schemas.guest_review_schema import GuestReviewCreate


class GuestReviewRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, review_data: GuestReviewCreate):

        review = GuestReview(**review_data.model_dump())

        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)

        return review

    def get_by_listing(self, listing_id: UUID) -> List[GuestReview]:

        return (
            self.db.query(GuestReview)
            .filter(GuestReview.listing_id == listing_id)
            .all()
        )