"""market_service: thin wrappers over tools/stock_data.py.

These functions normalize AkShare/pandas return values into JSON-safe dicts.
AkShare returns numpy/pandas scalar types (np.int64, np.float64, Timestamp)
that aren't JSON serializable, so everything is coerced here.
"""
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from tools import stock_data
from tools.news_fetcher import get_10jqka_news

# Simple in-process TTL cache for the news endpoint (network call per request
# otherwise; 60s is fresh enough for a "实时" ticker).
_news_cache: Dict[str, Any] = {}
_NEWS_TTL = 60.0


def get_market_news(limit: int = 10) -> List[Dict[str, Any]]:
    """同花顺实时新闻 (TTL-cached, 60s)."""
    now = time.time()
    cached = _news_cache.get("news")
    if cached and now - cached[0] < _NEWS_TTL:
        return cached[1][:limit]
    news = _json_safe(get_10jqka_news(limit=limit)) or []
    _news_cache["news"] = (now, news)
    return news


def _json_safe(obj: Any) -> Any:
    """Recursively convert pandas/numpy/Timestamp values to JSON-safe Python
    natives. NaN/Inf become None (JSON has no NaN)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return [_json_safe(r) for r in obj.to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return _json_safe(obj.to_dict())
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, datetime):
        return obj.isoformat()
    # numpy scalars
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            val = float(obj)
            return None if (math.isnan(val) or math.isinf(val)) else val
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [_json_safe(v) for v in obj.tolist()]
    except ImportError:
        pass
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    return obj


def get_market_indices() -> List[Dict[str, Any]]:
    """Major index quotes (上证/深证/创业板/科创50)."""
    return _json_safe(stock_data.get_market_indices())


def get_market_hot_sectors(limit: int = 5) -> List[Dict[str, Any]]:
    """Top-N leading industry sectors."""
    return _json_safe(stock_data.get_market_hot_sectors(limit=limit))


def get_market_sentiment() -> Dict[str, Any]:
    """Market breadth + limit-up/down counts + sentiment label."""
    return _json_safe(stock_data.get_market_sentiment())


def search(query: str) -> Dict[str, Any]:
    """Resolve a user query to either a stock code or a board (sector).

    Mirrors app.py:506-512 (_get_entity_info):
      - 6-digit string -> stock code
      - board name match -> sector
      - else -> search_stock_code by name
    """
    query = (query or "").strip()
    if not query:
        return {"type": "empty", "stock_code": None, "stock_name": None,
                "is_sector": False, "sector_type": "", "sector_cons": []}

    # 6-digit stock code
    if query.isdigit() and len(query) == 6:
        return {"type": "stock", "stock_code": query, "stock_name": query,
                "is_sector": False, "sector_type": "", "sector_cons": []}

    # board (sector) match first — mirrors _get_entity_info ordering
    board = stock_data.search_board_info(query)
    if board:
        cons = stock_data.get_board_cons(board["name"], board["type"])
        return {
            "type": "sector",
            "stock_code": board["code"],
            "stock_name": board["name"],
            "is_sector": True,
            "sector_type": board["type"],
            "sector_cons": _json_safe(cons) if cons is not None else [],
        }

    # stock name search
    code, name = stock_data.search_stock_code(query)
    if code:
        return {"type": "stock", "stock_code": code, "stock_name": name,
                "is_sector": False, "sector_type": "", "sector_cons": []}

    return {"type": "not_found", "stock_code": None, "stock_name": None,
            "is_sector": False, "sector_type": "", "sector_cons": []}


def get_cache_status(stock_code: Optional[str] = None) -> Dict[str, Any]:
    return _json_safe(stock_data.get_cache_status(stock_code))


def clear_cache(ttl_seconds: int = 300) -> None:
    stock_data.clear_akshare_cache(ttl_seconds=ttl_seconds)
