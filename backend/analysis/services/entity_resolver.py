"""entity_resolver: resolve a user query to a stock code or board (sector).

The three-way resolution logic (6-digit code -> board -> name search) lives in
market_service.search(); this module is a thin error-raising wrapper so the
analysis API can return 400 on unresolvable queries while /api/market/search
keeps its 200 + type:"not_found" semantics.
"""
from typing import Any, Dict

from backend.market.services.market_service import search


def resolve_entity(query: str) -> Dict[str, Any]:
    """Resolve a user query.

    Returns a dict with keys:
        stock_code, stock_name, is_sector, sector_type, sector_cons
    Raises ValueError if the query cannot be resolved.
    """
    info = search(query)
    if info.get("type") in ("not_found", "empty"):
        raise ValueError(f"未找到: {query}")
    return info
