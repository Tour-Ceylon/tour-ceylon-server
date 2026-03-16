from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.schemas.activity_schema import ActivityCreate


class ActivityRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, activity_data: ActivityCreate):

        activity = Activity(**activity_data.model_dump())

        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)

        return activity

    def get_by_listing(self, listing_id: UUID) -> Optional[Activity]:

        return (
            self.db.query(Activity)
            .filter(Activity.listing_id == listing_id)
            .first()
        )