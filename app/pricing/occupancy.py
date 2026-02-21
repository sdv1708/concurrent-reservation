from decimal import Decimal
from app.pricing.strategy import PricingStrategy


class OccupancyPricing(PricingStrategy):
    """Adds 20% when more than 80% of rooms for that date are already booked."""
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if inventory.total_count > 0:
            occupancy = inventory.book_count / inventory.total_count
            if occupancy > 0.8:
                price *= Decimal("1.20")
        return price
