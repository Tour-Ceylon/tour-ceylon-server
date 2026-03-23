from enum import Enum


class UserRole(str, Enum):
    TOURIST = "tourist"
    ADMIN = "admin"
    GUIDE = "guide"


class ListingType(str, Enum):
    STAY = "stay"
    TOUR = "tour"
    ACTIVITY = "activity"
    TRANSFER = "transfer"


class CurrencyType(str, Enum):
    LKR = "LKR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class BookingStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
