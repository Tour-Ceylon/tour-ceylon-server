"""Server-side totals for a booking inquiry (FLOW-3).

The browser used to send `subtotal` and `total`, and for a multi-night stay the
figure it sent was lower than the figure it displayed. The server now works the
totals out from the cart lines and ignores whatever the browser sends.

Rule (same as the customer site's `bookingTotals.ts` and `payments/pricing.py`):
  * a stay line costs `price x nights` (its `price` already covers every room);
  * every other line costs `price x travelers` (`travel_count`);
  * tax is 12% of the subtotal, rounded to cents.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from app.payments.pricing import nights_between

TAX_RATE = Decimal("0.12")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class InquiryTotals:
    subtotal: Decimal
    taxes: Decimal
    total: Decimal
    currency: str


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _is_stay_line(item) -> bool:
    return bool(getattr(item, "selected_rooms", None)) or getattr(item, "travel_date_end", None) is not None


def line_total(item) -> Decimal:
    price = Decimal(str(item.price))
    if _is_stay_line(item):
        nights = nights_between(item.travel_date, item.travel_date_end)
        return _money(price * nights)
    return _money(price * max(int(item.travel_count or 1), 1))


def compute_totals(cart_items: Iterable, fallback_currency: str = "USD") -> InquiryTotals:
    items = list(cart_items)
    subtotal = _money(sum((line_total(i) for i in items), Decimal(0)))
    taxes = _money(subtotal * TAX_RATE)
    currency = fallback_currency
    for item in items:
        code = getattr(item.base_currency, "value", item.base_currency)
        if code:
            currency = str(code)
            break
    return InquiryTotals(subtotal=subtotal, taxes=taxes, total=subtotal + taxes, currency=currency)
