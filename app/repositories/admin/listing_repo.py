from uuid import UUID

from sqlalchemy.orm import Session

from app.models.listing import Listing


class AdminDashboardListingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_listing(self, listing_data: dict) -> Listing:
        listing = Listing(**listing_data)
        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)
        return listing

    def get_listing(self, listing_id: UUID) -> Listing | None:
        return self.db.query(Listing).filter(Listing.id == listing_id).first()

    def get_all_listings(self) -> list[Listing]:
        return self.db.query(Listing).order_by(Listing.created_at.desc()).all()

    def update_listing(self, listing: Listing, updates: dict) -> Listing:
        for field, value in updates.items():
            setattr(listing, field, value)
        self.db.commit()
        self.db.refresh(listing)
        return listing

    def delete_listing(self, listing_id: UUID) -> bool:
        listing = self.get_listing(listing_id)
        if not listing:
            return False
        self.db.delete(listing)
        self.db.commit()
        return True

    def delete_all(self) -> None:
        self.db.query(Listing).delete()
        self.db.commit()
