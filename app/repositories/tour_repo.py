# Placeholder
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.tour import Tour
from app.schemas.tour_schema import TourCreate


class TourRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, tour_data: TourCreate):

        tour = Tour(**tour_data.model_dump())

        self.db.add(tour)
        self.db.commit()
        self.db.refresh(tour)

        return tour

    def get_by_listing(self, listing_id: UUID) -> Optional[Tour]:

        return (
            self.db.query(Tour)
            .filter(Tour.listing_id == listing_id)
            .first()
        )