from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.listing import Listing
from app.repositories.listing_repo import ListingRepository
from app.schemas.listing_schema import ListingCreate, ListingUpdate


class AdminDashboardListingRepository:
    def __init__(self, db: Session):
        self.db = db
        self.listing_repo = ListingRepository(db)

    def create_listing(self, listing_data: dict) -> Listing:
        return self.listing_repo.create(ListingCreate.model_validate(listing_data))

    def get_listing(self, listing_id: UUID) -> Listing | None:
        return self.listing_repo.get_by_id(listing_id)

    def get_all_listings(self) -> list[Listing]:
        return (
            self.db.query(Listing)
            .options(
                joinedload(Listing.destination),
                joinedload(Listing.media),
                joinedload(Listing.cover_media),
                joinedload(Listing.hotel_detail),
                joinedload(Listing.tour_detail),
                joinedload(Listing.safari_detail),
                joinedload(Listing.transfer_detail),
                selectinload(Listing.media_assets),
            )
            .order_by(Listing.created_at.desc())
            .all()
        )

    def update_listing(self, listing_id: UUID, updates: dict) -> Listing | None:
        return self.listing_repo.update(listing_id, ListingUpdate.model_validate(updates))

    def delete_listing(self, listing_id: UUID) -> bool:
        return self.listing_repo.delete(listing_id)

    def delete_all(self) -> None:
        self.db.query(Listing).delete()
        self.db.commit()
