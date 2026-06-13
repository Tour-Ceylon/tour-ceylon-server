from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.repositories.listing_repo import ListingRepository
from app.schemas.listing_schema import ListingCreate, ListingUpdate


from app.models.enum import UserRole

class AdminDashboardListingRepository:
    def __init__(self, db: Session):
        self.db = db
        self.listing_repo = ListingRepository(db)

    def _base_query(self):
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
                selectinload(Listing.variants).selectinload(ListingVariant.pricing_rules),
            )
        )

    def create_listing(self, listing_data: dict) -> Listing:
        listing = self.listing_repo.create(ListingCreate.model_validate(listing_data))
        return self.get_listing(listing.id)

    def get_listing(self, listing_id: UUID) -> Listing | None:
        return self._base_query().filter(Listing.id == listing_id).first()

    def get_all_listings(self, current_user) -> list[Listing]:
        query = self._base_query()
        role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
        if role == UserRole.VENDOR.value:
            query = query.filter(Listing.vendor_id == current_user.id)
        return query.order_by(Listing.created_at.desc()).all()

    def update_listing(self, listing_id: UUID, updates: dict) -> Listing | None:
        listing = self.listing_repo.update(listing_id, ListingUpdate.model_validate(updates))
        return self.get_listing(listing_id) if listing is not None else None

    def delete_listing(self, listing_id: UUID) -> bool:
        return self.listing_repo.delete(listing_id)

    def delete_all(self) -> None:
        self.db.query(Listing).delete()
        self.db.commit()

    def replace_variants(self, listing_id: UUID, variants: list[dict]) -> None:
        listing = self.get_listing(listing_id)
        if listing is None:
            return
        self.listing_repo._replace_variants(listing, variants)
        self.db.commit()
