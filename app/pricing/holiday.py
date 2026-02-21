from decimal import Decimal
from app.pricing.strategy import PricingStrategy


class HolidayPricing(PricingStrategy):
    """Adds 25% on weekends (Saturday=5, Sunday=6 in Python's weekday())."""
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if inventory.date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            price *= Decimal("1.25")
        return price
