"""Pagination helper for list endpoints (offset/limit style)."""
from ninja import Schema


class PaginatedOut(Schema):
    """Generic paginated response envelope."""
    items: list
    total: int
    page: int
    page_size: int


def paginate(qs, page: int = 1, page_size: int = 20):
    """Slice a Django queryset/list into a page. Returns (items, total)."""
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    total = qs.count() if hasattr(qs, "count") else len(qs)
    start = (page - 1) * page_size
    end = start + page_size
    items = list(qs[start:end]) if hasattr(qs, "__getitem__") else list(qs)[start:end]
    return items, total, page, page_size
