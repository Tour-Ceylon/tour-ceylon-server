from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.listingInclude import ListingInclude
from app.schemas.include_schema import ListingIncludeCreate


class ListingIncludeRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, include_data: ListingIncludeCreate) -> ListingInclude:

        db_include = ListingInclude(
            listing_id=include_data.listing_id,
            name=include_data.name
        )

        self.db.add(db_include)
        self.db.commit()
        self.db.refresh(db_include)

        return db_include

    def get_by_listing(self, listing_id: UUID) -> List[ListingInclude]:

        return (
            self.db.query(ListingInclude)
            .filter(ListingInclude.listing_id == listing_id)
            .all()
        )

    def delete_by_listing(self, listing_id: UUID):

        self.db.query(ListingInclude).filter(
            ListingInclude.listing_id == listing_id
        ).delete()

        self.db.commit()