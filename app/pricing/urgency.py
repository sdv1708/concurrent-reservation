from decimal import Decimal
from datetime import date
from app.pricing.strategy import PricingStrategy


class UrgencyPricing(PricingStrategy):
    """Adds 15% if the inventory date is within 7 days from today (last-minute booking)."""
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        days_away = (inventory.date - date.today()).days
        if 0 <= days_away <= 7:
            price *= Decimal("1.15")
        return price
