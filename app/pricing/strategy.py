from abc import ABC, abstractmethod
from decimal import Decimal


class PricingStrategy(ABC):
    """
    Abstract base for all pricing decorators.
    Every concrete class implements calculate(inventory) -> Decimal.
    """
    @abstractmethod
    def calculate(self, inventory) -> Decimal:
        ...
