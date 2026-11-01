"""Server-side price for a cart inquiry, rebuilt from database prices.

The browser sends its own prices and totals, so none of them can be charged as
they are. This module recomputes the amount the customer is shown (every line
at `price x nights`, plus 12% tax; see tour-ceylon-client `bookingTotals.ts`)
from the listing, room-type and variant prices stored here, and refuses to
price anything it cannot verify.
"""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.listing import Listing
from app.models.stay import StayProperty, StayRoomType
from app.payments.errors import PaymentError

TAX_RATE = Decimal("0.12")
CENT = Decimal("0.01")
TOLERANCE = Decimal("0.01")

UNVERIFIABLE = (
    "Online payment isn't available for this booking. "
    "Our team will contact you to arrange payment."
)
PRICE_CHANGED = "A price has changed since you added this to your cart. Please review your cart and try again."


@dataclass(frozen=True)
class PricedCart:
    amount: Decimal
    currency: str
    subtotal: Decimal
    taxes: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except Exception:
        return Decimal(0)


def _get(item: dict, snake: str, camel: str) -> Any:
    value = item.get(snake)
    return value if value is not None else item.get(camel)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def _to_date(value: Any) -> Optional[date]:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def nights_between(start: Any, end: Any) -> int:
    """Same rule as the client's nightsBetween: at least one night."""
    first, last = _to_date(start), _to_date(end)
    if not first or not last:
        return 1
    nights = (last - first).days
    return nights if nights > 0 else 1


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def _price_stay(db: Session, listing: Listing, item: dict, currency: str, nights: int) -> Decimal:
    stay = db.query(StayProperty).filter(StayProperty.listing_id == listing.id).first()
    if stay is None:
        raise PaymentError(409, UNVERIFIABLE)

    per_night = Decimal(0)
    for room in item.get("selected_rooms") or item.get("selectedRooms") or []:
        if not isinstance(room, dict):
            raise PaymentError(409, UNVERIFIABLE)
        try:
            room_id = UUID(str(room.get("roomId") or room.get("id")))
        except (ValueError, TypeError):
            raise PaymentError(409, UNVERIFIABLE)
        qty = int(_dec(room.get("qty") or 1))
        room_type = db.get(StayRoomType, room_id)
        if (
            qty < 1
            or room_type is None
            or room_type.property_id != stay.id
            or not room_type.base_price
            or _enum_value(room_type.currency) != currency
        ):
            raise PaymentError(409, UNVERIFIABLE)
        if not _close(_dec(room.get("price")), _dec(room_type.base_price)):
            raise PaymentError(409, PRICE_CHANGED)
        per_night += _dec(room_type.base_price) * qty

    if per_night <= 0:
        raise PaymentError(409, UNVERIFIABLE)
    if not _close(_dec(item.get("price")), per_night):
        raise PaymentError(409, PRICE_CHANGED)
    return _money(per_night * nights)


def _travelers(item: dict) -> int:
    count = int(_dec(_get(item, "travel_count", "travelCount")))
    return count if count >= 1 else 1


def _price_variant_listing(listing: Listing, item: dict, currency: str) -> Decimal:
    """Tours, packages, safaris and experiences are priced per person.

    The submitted price must be one of the listing's variant prices, and the
    line costs that price times the number of travelers (as the cart shows).
    """
    price = _dec(item.get("price"))
    amounts: List[Decimal] = []
    for variant in listing.variants or []:
        if getattr(variant, "is_active", True) is False:
            continue
        pricing = variant.pricing
        if not pricing or _enum_value(pricing.get("currency")) != currency:
            continue
        amounts.append(_dec(pricing.get("amount")))
    if not amounts:
        raise PaymentError(409, UNVERIFIABLE)
    if not any(_close(price, amount) for amount in amounts):
        raise PaymentError(409, PRICE_CHANGED)
    return _money(price * _travelers(item))


def price_cart(db: Session, cart_items: Any) -> PricedCart:
    items = [i for i in (cart_items or []) if isinstance(i, dict)]
    if not items or len(items) != len(cart_items):
        raise PaymentError(409, UNVERIFIABLE)

    subtotal = Decimal(0)
    currencies = set()
    for item in items:
        listing_id = str(_get(item, "listing_id", "listingId") or "")
        try:
            listing = db.get(Listing, UUID(listing_id))
        except (ValueError, TypeError):
            listing = None  # transfer-* and other non-listing lines cannot be verified
        if listing is None or getattr(listing, "is_active", True) is False:
            raise PaymentError(409, UNVERIFIABLE)

        currency = _enum_value(_get(item, "base_currency", "baseCurrency"))
        if not currency:
            raise PaymentError(409, UNVERIFIABLE)
        currencies.add(currency)

        if item.get("selected_rooms") or item.get("selectedRooms"):
            nights = nights_between(
                _get(item, "travel_date", "travelDate"), _get(item, "travel_date_end", "travelDateEnd")
            )
            subtotal += _price_stay(db, listing, item, currency, nights)
        else:
            subtotal += _price_variant_listing(listing, item, currency)

    if len(currencies) != 1:
        raise PaymentError(409, UNVERIFIABLE)

    subtotal = _money(subtotal)
    taxes = _money(subtotal * TAX_RATE)
    return PricedCart(amount=subtotal + taxes, currency=currencies.pop(), subtotal=subtotal, taxes=taxes)
