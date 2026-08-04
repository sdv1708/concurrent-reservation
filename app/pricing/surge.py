from decimal import Decimal
from app.pricing.strategy import PricingStrategy


class SurgePricing(PricingStrategy):
    """
    Applies the admin-set surge multiplier (inventory.surge_factor) when it's > 1.
    Factor defaults to 1 (no surge); only values above that raise the price here.
    """
    def __init__(self, wrapped: PricingStrategy):
        self._wrapped = wrapped

    def calculate(self, inventory) -> Decimal:
        price = self._wrapped.calculate(inventory)
        if Decimal(str(inventory.surge_factor)) > Decimal("1"):
            price *= Decimal(str(inventory.surge_factor))
        return price
