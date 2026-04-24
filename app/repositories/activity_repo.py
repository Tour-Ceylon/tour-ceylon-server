from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.safariDetail import SafariDetail
from app.schemas.activity_schema import ActivityCreate


class ActivityRepository:
    """Deprecated compatibility repository backed by SafariDetail."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, activity_data: ActivityCreate) -> SafariDetail:
        activity = SafariDetail(**activity_data.model_dump())
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def get_by_listing(self, listing_id: UUID) -> Optional[SafariDetail]:
        return (
            self.db.query(SafariDetail)
            .filter(SafariDetail.listing_id == listing_id)
            .first()
        )
