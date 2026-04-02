from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.guestReview import GuestReview
from app.models.listing import Listing
from app.models.reviewMetric import ReviewMetric
from app.models.room import Room


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
        return (
            self.db.query(Listing)
            .options(
                selectinload(Listing.rooms),
                selectinload(Listing.review_metrics),
                selectinload(Listing.guest_reviews),
            )
            .filter(Listing.id == listing_id)
            .first()
        )

    def get_all_listings(self) -> list[Listing]:
        return (
            self.db.query(Listing)
            .options(
                selectinload(Listing.rooms),
                selectinload(Listing.review_metrics),
                selectinload(Listing.guest_reviews),
            )
            .order_by(Listing.created_at.desc())
            .all()
        )

    def update_listing(self, listing: Listing, updates: dict) -> Listing:
        for field, value in updates.items():
            setattr(listing, field, value)
        self.db.commit()
        self.db.refresh(listing)
        return listing

    def replace_rooms(self, listing_id: UUID, rooms_payload: list[dict]) -> None:
        self.db.query(Room).filter(Room.listing_id == listing_id).delete()
        for room in rooms_payload:
            self.db.add(
                Room(
                    listing_id=listing_id,
                    name=room["name"],
                    amenities=room.get("amenities", []),
                    price_per_night=room["pricePerNight"],
                    available=room.get("available", True),
                )
            )
        self.db.commit()

    def replace_review_metrics(self, listing_id: UUID, metrics_payload: list[dict]) -> None:
        self.db.query(ReviewMetric).filter(ReviewMetric.listing_id == listing_id).delete()
        for metric in metrics_payload:
            self.db.add(
                ReviewMetric(
                    listing_id=listing_id,
                    label=metric["label"],
                    score=metric["score"],
                )
            )
        self.db.commit()

    def replace_guest_reviews(self, listing_id: UUID, reviews_payload: list[dict]) -> None:
        self.db.query(GuestReview).filter(GuestReview.listing_id == listing_id).delete()
        for review in reviews_payload:
            self.db.add(
                GuestReview(
                    listing_id=listing_id,
                    author=review["author"],
                    quote=review["quote"],
                )
            )
        self.db.commit()

    def delete_listing(self, listing_id: UUID) -> bool:
        listing = self.get_listing(listing_id)
        if not listing:
            return False
        self.db.query(Room).filter(Room.listing_id == listing_id).delete()
        self.db.query(ReviewMetric).filter(ReviewMetric.listing_id == listing_id).delete()
        self.db.query(GuestReview).filter(GuestReview.listing_id == listing_id).delete()
        self.db.delete(listing)
        self.db.commit()
        return True

    def delete_all(self) -> None:
        self.db.query(Room).delete()
        self.db.query(ReviewMetric).delete()
        self.db.query(GuestReview).delete()
        self.db.query(Listing).delete()
        self.db.commit()
