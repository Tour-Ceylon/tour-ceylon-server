from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enum import PricingRuleType
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.repositories.listing_repo import ListingRepository
from app.schemas.listing_schema import ListingCreate, ListingUpdate


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
        variants = listing_data.pop("variants", None)
        listing = self.listing_repo.create(ListingCreate.model_validate(listing_data))
        if variants is not None:
            self.replace_variants(listing.id, variants)
        return self.get_listing(listing.id)

    def get_listing(self, listing_id: UUID) -> Listing | None:
        return self._base_query().filter(Listing.id == listing_id).first()

    def get_all_listings(self) -> list[Listing]:
        return self._base_query().order_by(Listing.created_at.desc()).all()

    def update_listing(self, listing_id: UUID, updates: dict) -> Listing | None:
        variants = updates.pop("variants", None)
        listing = self.listing_repo.update(listing_id, ListingUpdate.model_validate(updates))
        if listing is None:
            return None
        if variants is not None:
            self.replace_variants(listing_id, variants)
        return self.get_listing(listing_id)

    def delete_listing(self, listing_id: UUID) -> bool:
        return self.listing_repo.delete(listing_id)

    def delete_all(self) -> None:
        self.db.query(Listing).delete()
        self.db.commit()

    def replace_variants(self, listing_id: UUID, variants: list[dict]) -> None:
        listing = self.get_listing(listing_id)
        if listing is None:
            return

        for existing_variant in list(listing.variants or []):
            self.db.delete(existing_variant)
        self.db.flush()

        for variant_payload in variants:
            pricing_payload = variant_payload["pricing"]
            variant = ListingVariant(
                listing_id=listing_id,
                name=variant_payload["name"],
                booking_unit=variant_payload["booking_unit"],
                capacity_min=variant_payload.get("capacity_min"),
                capacity_max=variant_payload.get("capacity_max"),
                is_default=variant_payload.get("is_default", False),
            )
            self.db.add(variant)
            self.db.flush()
            variant.pricing_rules.append(
                PricingRule(
                    amount=pricing_payload["amount"],
                    currency=pricing_payload["currency"],
                    priority=pricing_payload["priority"],
                    pricing_rule_type=PricingRuleType.FIXED,
                    min_guest=variant_payload.get("capacity_min") or 1,
                    max_guest=variant_payload.get("capacity_max") or 999999,
                )
            )

        self.db.commit()
