from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin_dashboard import AdminListingDetails
from app.models.listing import Listing


class AdminDashboardListingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_listing(self, listing_data: dict) -> Listing:
        listing = Listing(**listing_data)
        self.db.add(listing)
        self.db.flush()
        return listing

    def create_details(self, listing_id: UUID, category: str, payload: dict) -> AdminListingDetails:
        details = AdminListingDetails(
            listing_id=listing_id,
            category=category,
            payload=payload,
        )
        self.db.add(details)
        self.db.commit()
        self.db.refresh(details)
        return details

    def get_detail(self, listing_id: UUID) -> AdminListingDetails | None:
        return self.db.query(AdminListingDetails).filter(AdminListingDetails.listing_id == listing_id).first()

    def get_detail_by_category(self, category: str, listing_id: UUID) -> AdminListingDetails | None:
        return (
            self.db.query(AdminListingDetails)
            .filter(
                AdminListingDetails.category == category,
                AdminListingDetails.listing_id == listing_id,
            )
            .first()
        )

    def get_listing(self, listing_id: UUID) -> Listing | None:
        return self.db.query(Listing).filter(Listing.id == listing_id).first()

    def get_all_details(self) -> list[AdminListingDetails]:
        return self.db.query(AdminListingDetails).order_by(AdminListingDetails.created_at.desc()).all()

    def update_listing(self, listing: Listing, updates: dict) -> Listing:
        for field, value in updates.items():
            setattr(listing, field, value)
        self.db.flush()
        return listing

    def update_detail(self, detail: AdminListingDetails, payload: dict) -> AdminListingDetails:
        detail.payload = payload
        self.db.commit()
        self.db.refresh(detail)
        return detail

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, instance: Listing | AdminListingDetails) -> None:
        self.db.refresh(instance)

    def delete_listing(self, listing_id: UUID) -> bool:
        detail = self.get_detail(listing_id)
        listing = self.get_listing(listing_id)
        if not detail or not listing:
            return False
        self.db.delete(detail)
        self.db.delete(listing)
        self.db.commit()
        return True

    def delete_all(self) -> None:
        detail_rows = self.db.query(AdminListingDetails).all()
        listing_ids = [row.listing_id for row in detail_rows]
        self.db.query(AdminListingDetails).delete()
        if listing_ids:
            self.db.query(Listing).filter(Listing.id.in_(listing_ids)).delete(synchronize_session=False)
        self.db.commit()

