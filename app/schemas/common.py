from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """
    Generic paginated response — reuse for any list endpoint.
    Example: PageResponse[HotelPriceOut]

    Usage in a route:
        content = hotel_service.search(...)
        return PageResponse(content=content, total_elements=total,
                            total_pages=total // size, page=page, size=size)
    """
    content: List[T]
    total_elements: int
    total_pages: int
    page: int
    size: int
