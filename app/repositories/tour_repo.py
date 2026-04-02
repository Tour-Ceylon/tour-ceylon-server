from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.tourDetail import TourDetail
from app.schemas.tour_schema import TourCreate


class TourRepository:
    """Deprecated compatibility repository backed by TourDetail."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, tour_data: TourCreate) -> TourDetail:
        tour = TourDetail(**tour_data.model_dump())
        self.db.add(tour)
        self.db.commit()
        self.db.refresh(tour)
        return tour

    def get_by_listing(self, listing_id: UUID) -> Optional[TourDetail]:
        return (
            self.db.query(TourDetail)
            .filter(TourDetail.listing_id == listing_id)
            .first()
        )
