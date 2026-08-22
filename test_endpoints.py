from app.config.database import get_db
from app.repositories.listing_repo import ListingRepository
from app.services.package_service import PackageService
from app.schemas.listing_schema import ListingSearchParams
from app.models.enum import ListingType, ListingStatus

db = next(get_db())
listing_repo = ListingRepository(db)
package_service = PackageService(db)

# 1. Search experiences
params = ListingSearchParams(
    listing_type=ListingType.EXPERIENCE,
    status=ListingStatus.PUBLISHED,
    is_active=True,
    page=1,
    per_page=4
)
listings, total = listing_repo.search(params)
print(f"Experiences found: {len(listings)} (Total: {total})")
for l in listings:
    print(f"- {l.title} (Status: {l.status}, Active: {l.is_active})")

# 2. Search hotels
params_hotel = ListingSearchParams(
    listing_type=ListingType.HOTEL,
    status=ListingStatus.PUBLISHED,
    is_active=True,
    page=1,
    per_page=100
)
listings_hotel, total_hotel = listing_repo.search(params_hotel)
print(f"Hotels found: {len(listings_hotel)} (Total: {total_hotel})")
for l in listings_hotel:
    print(f"- {l.title} (Status: {l.status}, Active: {l.is_active})")

# 3. Packages
packages = package_service.get_active_packages()
print(f"Active Packages found: {len(packages)}")
for p in packages:
    print(f"- {p.title} (Status: {p.status}, Active: {p.is_active if hasattr(p, 'is_active') else 'N/A'})")

db.close()
