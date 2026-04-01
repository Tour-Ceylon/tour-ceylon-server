from enum import Enum


class UserRole(str, Enum):
    TOURIST = "tourist"
    ADMIN = "admin"
    SUPPORT = "support"
    VENDOR = "vendor"


class ListingType(str, Enum):
    TOUR = "tour"
    TRANSFER = "transfer"
    SAFARI = "safari"
    HOTEL = "hotel"


class ListingStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CurrencyCode(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AUD = "AUD"
    INR = "INR"
    CNY = "CNY"
    LKR = "LKR"

class BookingUnit(str, Enum):
    PER_PERSON = "per_person"
    PER_GROUP = "per_group"
    PER_VEHICLE = "per_vehicle"
    PER_ROOM = "per_room"
    PER_DAY = "per_day"
    PER_SEAT = "per_seat"
    PER_PACKAGE = "per_package"

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    MANUAL = "manual"


class PaymentTransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PricingRuleType(str, Enum):
    FIXED = "fixed"
    PER_PERSON = "per_person"
    PER_CHILD = "per_child"
    PER_GROUP = "per_group"
    PER_ROOM = "per_room"
    PER_DAY = "per_day"
    PER_NIGHT = "per_night"
    PER_VEHICLE = "per_vehicle"
    SEASONAL_OVERRIDE = "seasonal_override"


class AvailabilityStatus(str, Enum):
    OPEN = "open"
    LIMITED = "limited"
    SOLD_OUT = "sold_out"
    BLOCKED = "blocked"


class ReviewStatus(str, Enum):
    PUBLISHED = "published"
    HIDDEN = "hidden"
    PENDING = "pending"

class CancellationPolicyType(str, Enum):
    FLEXIBLE = "flexible"
    MODERATE = "moderate"
    STRICT = "strict"
    CUSTOM = "custom"
    NON_REFUNDABLE = "non_refundable"

class PenaltyType(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    FULL_AMOUNT = "full_amount"


class ChangedByType(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class DestinationType(str, Enum):
    COUNTRY = "country"
    PROVINCE = "province"
    DISTRICT = "district"
    CITY = "city"
    AREA = "area"
    ATTRACTION = "attraction"
    AIRPORT = "airport"
    HOTEL_ZONE = "hotel_zone"

class SafariType(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
    FULL_DAY = "full_day"
    PRIVATE = "private"
    SHARED = "shared"

class TransferLocationType(str, Enum):
    AIRPORT = "airport"
    HOTEL = "hotel"
    CITY = "city"
    LANDMARK = "landmark"
    STATION = "station"
    CUSTOM = "custom"