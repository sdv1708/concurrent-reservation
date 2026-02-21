from decimal import Decimal
from app.pricing.strategy import PricingStrategy


class SurgePricing(PricingStrategy):
    """
    Applies the admin-set surge multiplier when surge_factor > 1.
    Wraps BasePricing — calls it first, then applies its own adjustment.

    Decorator pattern: each layer calls self._wrapped.calculate() first,
    then optionally modifies the result before returning it.
    """
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if Decimal(str(inventory.surge_factor)) > Decimal("1"):
            price *= Decimal(str(inventory.surge_factor))
        return price
