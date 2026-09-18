from app.config.database import get_db
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant

db = next(get_db())
listings = db.query(Listing).all()

print(f"Total Listings: {len(listings)}")
for l in listings:
    print(f"\nListing ID: {l.id}")
    print(f"- Title: '{l.title}'")
    print(f"- Type: {l.listing_type}")
    print(f"- Status: {l.status}")
    print(f"- Active: {l.is_active}")
    print(f"- Variants Count: {len(l.variants) if l.variants else 0}")
    for v in (l.variants or []):
        print(f"  * Variant: '{v.name}' (Cap Min: {v.capacity_min}, Cap Max: {v.capacity_max}, Default: {v.is_default})")

db.close()
