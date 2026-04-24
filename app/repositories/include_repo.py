from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.include_schema import ListingIncludeCreate


class ListingIncludeRepository:
    """Legacy repository retained for compatibility after listing include model removal."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, include_data: ListingIncludeCreate):
        raise NotImplementedError("ListingIncludeRepository is deprecated; includes should be modeled through listing detail payloads.")

    def get_by_listing(self, listing_id: UUID) -> list:
        return []

    def delete_by_listing(self, listing_id: UUID):
        return None
