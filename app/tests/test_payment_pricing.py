from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.enum import BookingUnit, CurrencyCode, ListingStatus, ListingType, PricingRuleType
from app.models.listing import Listing
from app.models.listingVariant import ListingVariant
from app.models.pricingRule import PricingRule
from app.models.stay import StayProperty, StayRoomType
from app.payments import pricing
from app.payments.errors import PaymentError


@compiles(PGUUID, "sqlite")
def _uuid(_t, _c, **_kw):
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _jsonb(_t, _c, **_kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(_t, _c, **_kw):
    return "JSON"


TABLES = ("listings", "listing_variants", "pricing_rules", "stay_properties", "stay_room_types")


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in TABLES])
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()
    engine.dispose()


def make_listing(db, listing_type, currency="USD"):
    listing = Listing(
        destination_id=uuid4(),
        listing_type=listing_type,
        title="Test listing",
        status=ListingStatus.PUBLISHED,
        base_currency=CurrencyCode(currency),
    )
    db.add(listing)
    db.flush()
    return listing


def add_variant(db, listing, name, amount, currency="USD"):
    variant = ListingVariant(listing_id=listing.id, name=name, booking_unit=BookingUnit.PER_GROUP)
    db.add(variant)
    db.flush()
    db.add(
        PricingRule(
            variant_id=variant.id,
            pricing_rule_type=PricingRuleType.FIXED,
            min_guest=1,
            max_guest=10,
            amount=amount,
            currency=CurrencyCode(currency),
            priority=1,
        )
    )
    db.flush()
    return variant


def make_stay(db, rooms):
    listing = make_listing(db, ListingType.HOTEL)
    prop = StayProperty(listing_id=listing.id, name="Test Hotel", property_type="hotel")
    db.add(prop)
    db.flush()
    created = []
    for name, price in rooms:
        room = StayRoomType(property_id=prop.id, name=name, base_price=Decimal(price), currency="USD")
        db.add(room)
        created.append(room)
    db.flush()
    return listing, created


def stay_item(listing, rooms_with_qty, per_night, start="2027-03-01", end="2027-03-04", **overrides):
    item = {
        "listing_id": str(listing.id),
        "title": "Test Hotel",
        "travel_date": start,
        "travel_date_end": end,
        "travel_count": sum(q for _, q in rooms_with_qty),
        "price": per_night,
        "base_currency": "USD",
        "selected_rooms": [
            {"roomId": str(r.id), "qty": q, "price": float(r.base_price)} for r, q in rooms_with_qty
        ],
    }
    item.update(overrides)
    return item


def test_stay_priced_per_night_rooms_and_nights_with_tax(db):
    listing, (deluxe, suite) = make_stay(db, [("Deluxe", "100.00"), ("Suite", "250.50")])
    # 2 x Deluxe + 1 x Suite = 450.50 a night, 3 nights = 1351.50, tax 12% = 162.18
    item = stay_item(listing, [(deluxe, 2), (suite, 1)], per_night=450.50)
    priced = pricing.price_cart(db, [item])
    assert priced.subtotal == Decimal("1351.50")
    assert priced.taxes == Decimal("162.18")
    assert priced.amount == Decimal("1513.68")
    assert priced.currency == "USD"


def test_stay_one_night_when_dates_missing(db):
    listing, (room,) = make_stay(db, [("Deluxe", "80.00")])
    item = stay_item(listing, [(room, 1)], per_night=80, start="2027-03-01", end=None)
    assert pricing.price_cart(db, [item]).subtotal == Decimal("80.00")


def test_stay_price_tampered_is_rejected(db):
    listing, (room,) = make_stay(db, [("Deluxe", "100.00")])
    item = stay_item(listing, [(room, 1)], per_night=10)
    item["selected_rooms"][0]["price"] = 10
    with pytest.raises(PaymentError) as err:
        pricing.price_cart(db, [item])
    assert err.value.status_code == 409 and "price" in err.value.detail.lower()


def test_stay_total_price_field_tampered_is_rejected(db):
    listing, (room,) = make_stay(db, [("Deluxe", "100.00")])
    item = stay_item(listing, [(room, 2)], per_night=50)  # real per-night is 200
    with pytest.raises(PaymentError):
        pricing.price_cart(db, [item])


def test_room_from_another_property_is_rejected(db):
    listing, _ = make_stay(db, [("Deluxe", "100.00")])
    _, (other_room,) = make_stay(db, [("Other", "100.00")])
    with pytest.raises(PaymentError):
        pricing.price_cart(db, [stay_item(listing, [(other_room, 1)], per_night=100)])


def test_safari_variant_price_matches(db):
    listing = make_listing(db, ListingType.SAFARI)
    add_variant(db, listing, "Morning jeep", 120.0)
    add_variant(db, listing, "Evening jeep", 95.5)
    item = {"listing_id": str(listing.id), "title": "Safari", "travel_date": "2027-03-01", "travel_count": 1,
            "price": 95.5, "base_currency": "USD"}
    priced = pricing.price_cart(db, [item])
    assert priced.subtotal == Decimal("95.50")
    assert priced.amount == Decimal("106.96")  # 95.50 + 11.46


def test_package_price_must_be_a_listed_variant_price(db):
    listing = make_listing(db, ListingType.TOUR)
    add_variant(db, listing, "Standard", 1000.0)
    ok = {"listing_id": str(listing.id), "title": "Tour", "travel_date": "2027-03-01", "travel_count": 1,
          "price": 1000, "base_currency": "USD"}
    assert pricing.price_cart(db, [ok]).amount == Decimal("1120.00")
    cheap = {**ok, "price": 250}
    with pytest.raises(PaymentError) as err:
        pricing.price_cart(db, [cheap])
    assert err.value.status_code == 409


def test_variant_in_other_currency_does_not_count(db):
    listing = make_listing(db, ListingType.EXPERIENCE)
    add_variant(db, listing, "Cooking class", 50.0, currency="LKR")
    item = {"listing_id": str(listing.id), "title": "Class", "travel_date": "2027-03-01", "travel_count": 1,
            "price": 50, "base_currency": "USD"}
    with pytest.raises(PaymentError):
        pricing.price_cart(db, [item])


def test_unverifiable_lines_block_online_payment(db):
    for item in (
        {"listing_id": "transfer-sedan", "title": "Transfer", "price": 40, "base_currency": "USD"},
        {"listing_id": str(uuid4()), "title": "Missing", "price": 40, "base_currency": "USD"},
    ):
        with pytest.raises(PaymentError) as err:
            pricing.price_cart(db, [item])
        assert "isn't available" in err.value.detail
    with pytest.raises(PaymentError):
        pricing.price_cart(db, [])


def test_mixed_currencies_blocked(db):
    usd = make_listing(db, ListingType.TOUR)
    add_variant(db, usd, "A", 100.0, "USD")
    lkr = make_listing(db, ListingType.TOUR, "LKR")
    add_variant(db, lkr, "B", 100.0, "LKR")
    items = [
        {"listing_id": str(usd.id), "title": "A", "price": 100, "base_currency": "USD", "travel_date": "2027-03-01", "travel_count": 1},
        {"listing_id": str(lkr.id), "title": "B", "price": 100, "base_currency": "LKR", "travel_date": "2027-03-01", "travel_count": 1},
    ]
    with pytest.raises(PaymentError):
        pricing.price_cart(db, items)


def test_nights_between_matches_client_rule():
    assert pricing.nights_between("2027-03-01", "2027-03-04") == 3
    assert pricing.nights_between("2027-03-01T10:00:00", "2027-03-02T10:00:00") == 1
    assert pricing.nights_between("2027-03-01", "2027-03-01") == 1
    assert pricing.nights_between("2027-03-04", "2027-03-01") == 1
    assert pricing.nights_between(None, None) == 1


def test_per_person_price_is_multiplied_by_travelers(db):
    listing = make_listing(db, ListingType.EXPERIENCE)
    add_variant(db, listing, "Walking tour", 25.0)
    item = {"listing_id": str(listing.id), "title": "Walk", "travel_date": "2027-03-01", "travel_count": 2,
            "price": 25, "base_currency": "USD"}
    priced = pricing.price_cart(db, [item])
    assert priced.subtotal == Decimal("50.00")
    assert priced.amount == Decimal("56.00")  # 50.00 + 6.00 tax


def test_three_item_cart_from_the_bug_report(db):
    """45 + 1320 + 25 per person, two travelers each: 2780 before tax, which the old server check also expects."""
    items = []
    for price in (45.0, 1320.0, 25.0):
        listing = make_listing(db, ListingType.TOUR)
        add_variant(db, listing, "Standard", price)
        items.append({"listing_id": str(listing.id), "title": "Item", "travel_date": "2026-11-01", "travel_count": 2,
                      "price": price, "base_currency": "USD"})
    priced = pricing.price_cart(db, items)
    assert priced.subtotal == Decimal("2780.00")
    assert priced.amount == Decimal("3113.60")
