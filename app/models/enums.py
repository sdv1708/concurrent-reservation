from enum import Enum


class RoleEnum(str, Enum):
    GUEST         = "GUEST"
    HOTEL_MANAGER = "HOTEL_MANAGER"
    ADMIN         = "ADMIN"


class GenderEnum(str, Enum):
    MALE   = "MALE"
    FEMALE = "FEMALE"
    OTHER  = "OTHER"


class BookingStatusEnum(str, Enum):
    RESERVED         = "RESERVED"           # inventory held, payment not started
    GUESTS_ADDED     = "GUESTS_ADDED"       # guest list attached to booking
    PAYMENTS_PENDING = "PAYMENTS_PENDING"   # Stripe checkout session created
    CONFIRMED        = "CONFIRMED"          # payment webhook received — booking is live
    CANCELLED        = "CANCELLED"          # cancelled + refunded


class PaymentStatusEnum(str, Enum):
    PENDING   = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
