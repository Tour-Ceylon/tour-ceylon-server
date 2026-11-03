from enum import Enum


class PaymentStatus(str, Enum):
    INITIATED = "initiated"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CHARGEDBACK = "chargedback"


# Statuses a payment never leaves (apart from SUCCEEDED -> CHARGEDBACK).
FINAL_STATUSES = frozenset(
    {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.CHARGEDBACK,
    }
)


class TargetType(str, Enum):
    TRANSPORT_BOOKING = "transport_booking"
    BOOKING_INQUIRY = "booking_inquiry"
