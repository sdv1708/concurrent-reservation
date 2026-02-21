from decimal import Decimal
from app.pricing.strategy import PricingStrategy


class BasePricing(PricingStrategy):
    """
    The innermost layer of the pricing chain.
    Returns: inventory.price (base room price for that date, set at inventory creation).
    Note: surge_factor is applied separately by SurgePricing — not here.
    """
    def calculate(self, inventory) -> Decimal:
        return Decimal(str(inventory.price))
