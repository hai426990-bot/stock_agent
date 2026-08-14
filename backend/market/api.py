"""Market dashboard API: indices, hot sectors, sentiment, search, news."""
from typing import Any, Dict, List, Optional

from ninja import Router, Schema

from backend.market.services.market_service import (
    get_market_indices,
    get_market_hot_sectors,
    get_market_sentiment,
    search,
    get_cache_status,
    clear_cache,
    get_market_news,
)

router = Router()


class SearchOut(Schema):
    type: str
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    is_sector: bool = False
    sector_type: str = ""
    sector_cons: List[Any] = []


class CacheStatusOut(Schema):
    cache_file: Optional[str] = None
    cache_size: Optional[int] = None
    data_sources: Optional[Dict[str, Any]] = None


@router.get("/indices")
def indices(request):
    """Major market index quotes."""
    try:
        return {"indices": get_market_indices()}
    except Exception as e:
        return {"indices": [], "error": str(e)}


@router.get("/hot-sectors")
def hot_sectors(request, limit: int = 5):
    """Leading industry sectors."""
    try:
        return {"sectors": get_market_hot_sectors(limit=limit)}
    except Exception as e:
        return {"sectors": [], "error": str(e)}


@router.get("/sentiment")
def sentiment(request):
    """Market breadth + sentiment label."""
    try:
        return get_market_sentiment() or {}
    except Exception as e:
        return {"error": str(e)}


@router.get("/search", response=SearchOut)
def search_endpoint(request, q: str):
    """Resolve a query to a stock code or board (sector)."""
    try:
        return SearchOut(**search(q))
    except ValueError:
        return SearchOut(type="error")


@router.get("/cache/status", response=CacheStatusOut)
def cache_status(request, stock_code: Optional[str] = None):
    """AkShare cache status."""
    return CacheStatusOut(**(get_cache_status(stock_code) or {}))


@router.delete("/cache")
def cache_clear(request, ttl_seconds: int = 300):
    """Clear expired AkShare cache entries."""
    clear_cache(ttl_seconds=ttl_seconds)
    return {"message": "cache cleared"}


@router.get("/news")
def market_news(request, limit: int = 10):
    """同花顺实时新闻."""
    try:
        return {"news": get_market_news(limit=limit)}
    except Exception as e:
        return {"news": [], "error": str(e)}
