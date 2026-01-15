from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
import os
import re
import xml.etree.ElementTree as ET

import httpx


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_news_item(
    *,
    title: str,
    content: str,
    published_at: str = "",
    source: str = "",
    url: str = "",
) -> Dict[str, Any]:
    return {
        "新闻标题": title,
        "新闻内容": content,
        "发布时间": published_at,
        "来源": source,
        "链接": url,
    }


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_rss_items(
    urls: Iterable[str],
    *,
    timeout_s: float = 10.0,
    limit_per_feed: int = 20,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    headers = {"User-Agent": "stock_agent/1.0"}
    with httpx.Client(timeout=timeout_s, headers=headers, follow_redirects=True) as client:
        for url in urls:
            url = _safe_text(url)
            if not url:
                continue
            try:
                resp = client.get(url)
                resp.raise_for_status()
                items.extend(_parse_rss_or_atom(resp.text, source=url, limit=limit_per_feed))
            except Exception:
                continue
    return items


def _parse_rss_or_atom(xml_text: str, *, source: str, limit: int) -> List[Dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    rss_items = root.findall(".//channel/item")
    if rss_items:
        out: List[Dict[str, Any]] = []
        for node in rss_items[:limit]:
            title = _safe_text(node.findtext("title"))
            link = _safe_text(node.findtext("link"))
            pub = _safe_text(node.findtext("pubDate"))
            desc = _safe_text(node.findtext("description"))
            content = _strip_html(desc) if desc else ""
            if title or content:
                out.append(_to_news_item(title=title, content=content, published_at=pub, source=source, url=link))
        return out

    atom_entries = root.findall(".//atom:entry", namespaces=ns)
    if atom_entries:
        out = []
        for node in atom_entries[:limit]:
            title = _safe_text(node.findtext("atom:title", namespaces=ns))
            updated = _safe_text(node.findtext("atom:updated", namespaces=ns))
            summary = _safe_text(node.findtext("atom:summary", namespaces=ns))
            link_el = node.find("atom:link", namespaces=ns)
            link = _safe_text(link_el.get("href") if link_el is not None else "")
            content = _strip_html(summary) if summary else ""
            if title or content:
                out.append(_to_news_item(title=title, content=content, published_at=updated, source=source, url=link))
        return out

    return []


def fetch_reddit_search_items(
    query: str,
    *,
    limit: int = 20,
    timeout_s: float = 10.0,
) -> List[Dict[str, Any]]:
    query = _safe_text(query)
    if not query:
        return []
    url = "https://www.reddit.com/search.json"
    params = {"q": query, "sort": "new", "limit": int(limit)}
    headers = {"User-Agent": "stock_agent/1.0"}
    try:
        with httpx.Client(timeout=timeout_s, headers=headers, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for child in (data.get("data", {}) or {}).get("children", [])[:limit]:
        item = child.get("data", {}) or {}
        title = _safe_text(item.get("title"))
        text = _safe_text(item.get("selftext"))
        created = item.get("created_utc")
        created_str = ""
        if isinstance(created, (int, float)):
            created_str = datetime.utcfromtimestamp(created).isoformat() + "Z"
        permalink = _safe_text(item.get("permalink"))
        link = f"https://www.reddit.com{permalink}" if permalink else ""
        if title or text:
            out.append(_to_news_item(title=title, content=text, published_at=created_str, source="reddit", url=link))
    return out


def fetch_x_search_items(
    query: str,
    *,
    bearer_token: Optional[str] = None,
    limit: int = 20,
    timeout_s: float = 10.0,
) -> List[Dict[str, Any]]:
    query = _safe_text(query)
    token = bearer_token or os.getenv("X_BEARER_TOKEN", "")
    if not query or not token:
        return []

    url = "https://api.x.com/2/tweets/search/recent"
    params = {"query": query, "max_results": min(100, int(limit)), "tweet.fields": "created_at"}
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=timeout_s, headers=headers, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for tw in (data.get("data", []) or [])[:limit]:
        text = _safe_text(tw.get("text"))
        out.append(
            _to_news_item(
                title=text[:120],
                content=text,
                published_at=_safe_text(tw.get("created_at")),
                source="x",
                url="",
            )
        )
    return out

