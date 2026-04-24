from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.guest_review_schema import GuestReviewCreate


class GuestReviewRepository:
    """Legacy repository retained for compatibility after guest review model removal."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, review_data: GuestReviewCreate):
        raise NotImplementedError("GuestReviewRepository is deprecated; guest reviews are no longer stored as a standalone model.")

    def get_by_listing(self, listing_id: UUID) -> list:
        return []
