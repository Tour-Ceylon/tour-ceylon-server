from enum import Enum


class UserRole(str, Enum):
    TOURIST = "tourist"
    GUIDE = "guide"
    ADMIN = "admin"


class BookingStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ListingType(str, Enum):
    TOUR = "tour"
    HOTEL = "hotel"
    TRANSPORT = "transport"
    TRANSFER = "transfer"
    ACTIVITY = "activity"
    SAFARI = "safari"


class ListingStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CurrencyType(str, Enum):
    LKR = "LKR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    LIMITED = "limited"


class BookingUnit(str, Enum):
    PERSON = "person"
    ROOM = "room"
    VEHICLE = "vehicle"
    GROUP = "group"


class CurrencyCode(str, Enum):
    LKR = "LKR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class PaymentTransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class DestinationType(str, Enum):
    CITY = "city"
    PROVINCE = "province"
    ATTRACTION = "attraction"
    REGION = "region"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class PropertyType(str, Enum):
    HOTEL = "hotel"
    RESORT = "resort"
    VILLA = "villa"
    GUESTHOUSE = "guesthouse"
    APARTMENT = "apartment"


class SafariType(str, Enum):
    GAME_DRIVE = "game_drive"
    WALKING_SAFARI = "walking_safari"
    BOAT_SAFARI = "boat_safari"
    BIRD_WATCHING = "bird_watching"


class TransferLocationType(str, Enum):
    AIRPORT = "airport"
    HOTEL = "hotel"
    ATTRACTION = "attraction"
    CITY = "city"


class ChangedByType(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


class CancellationPolicyType(str, Enum):
    FLEXIBLE = "flexible"
    MODERATE = "moderate"
    STRICT = "strict"
    NON_REFUNDABLE = "non_refundable"


class PenaltyType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    NO_PENALTY = "no_penalty"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PricingRuleType(str, Enum):
    SEASONAL = "seasonal"
    GROUP_DISCOUNT = "group_discount"
    EARLY_BIRD = "early_bird"
    LAST_MINUTE = "last_minute"


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    PAYHERE = "payhere"
    BANK_TRANSFER = "bank_transfer"
