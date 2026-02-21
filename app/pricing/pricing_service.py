from decimal import Decimal
from typing import List
from app.pricing.base import BasePricing
from app.pricing.surge import SurgePricing
from app.pricing.occupancy import OccupancyPricing
from app.pricing.urgency import UrgencyPricing
from app.pricing.holiday import HolidayPricing


def build_pricing_chain():
    """
    Assembles the decorator chain in the correct order.
    Order matters — each layer wraps the previous one and modifies its result.

    Execution order (innermost to outermost):
      Base → Surge → Occupancy → Urgency → Holiday
    """
    s = BasePricing()
    s = SurgePricing(s)
    s = OccupancyPricing(s)
    s = UrgencyPricing(s)
    s = HolidayPricing(s)
    return s


def calculate_dynamic_price(inventory) -> Decimal:
    """Get the final price for a single inventory row (one room, one date)."""
    return build_pricing_chain().calculate(inventory)


def calculate_total_price(inventories: List) -> Decimal:
    """
    Sum dynamic price across all inventory rows in a booking date range.
    This gives the price for ONE room across all booked nights.
    Multiply by rooms_count in the booking service to get the total.

    Example: 3-night stay, $100/night average → $300 for one room
             Booking 2 rooms → $600 total
    """
    chain = build_pricing_chain()
    return sum(chain.calculate(inv) for inv in inventories) or Decimal("0")
