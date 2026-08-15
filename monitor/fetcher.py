"""
异动候选快照抓取器

两个数据源通道 (自动回退):
    1. 新浪排行榜 (默认): vip.stock.finance.sina.com.cn Market_Center 榜单接口
       4 个单页请求 (涨幅/跌幅/成交额/换手率 Top100)，覆盖全部可能的异动标的，
       单轮约 2-4 秒。字段: 涨跌幅/成交额/换手率/振幅(由高低价计算)。
    2. 东方财富 clist (可选): 6 个单页请求，额外提供量比/涨速字段；
       部分网络环境下不可达 (或被屏蔽)，通过 --data-source 切换。

两条通道均优先直连 (本机系统代理对国内财经数据源常不可用/不稳定)，
直连失败时回退系统代理。
"""
import time
from typing import Any, Dict

import requests

from tools.retry import retry

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "https://finance.sina.com.cn",
}

# ---------------------------------------------------------------------------
# 新浪榜单通道
# ---------------------------------------------------------------------------
SINA_RANK_URL = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                 "Market_Center.getHQNodeData")

# (排序字段, 升/降序, 用途)
SINA_RANK_LISTS = [
    ("changepercent", 0, "涨幅榜"),
    ("changepercent", 1, "跌幅榜"),
    ("amount", 0, "成交额榜"),
    ("turnoverratio", 0, "换手率榜"),
]


@retry(max_retries=3, delay=1.0, backoff=2)
def _fetch_sina_rank(sort: str, asc: int) -> list:
    """拉取新浪单个排行榜 (单页 100 条)。"""
    params = {
        "page": 1,
        "num": 100,
        "sort": sort,
        "asc": str(asc),
        "node": "hs_a",
        "symbol": "",
        "_s_r_a": "page",
    }
    for proxies in ({"http": None, "https": None}, None):  # None -> 系统代理
        try:
            resp = requests.get(SINA_RANK_URL, params=params, headers=HEADERS,
                                timeout=10, proxies=proxies)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except (requests.RequestException, ValueError):
            if proxies is None:
                raise
            continue
    return []


def _sina_to_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """新浪榜单行 -> 标准化快照行。"""
    high = _to_float(raw.get("high"))
    low = _to_float(raw.get("low"))
    settlement = _to_float(raw.get("settlement"))
    amplitude = ((high - low) / settlement * 100.0) if settlement > 0 else 0.0
    return {
        "code": str(raw.get("code", "")).zfill(6),
        "name": str(raw.get("name", "")),
        "price": _to_float(raw.get("trade")),
        "pct": _to_float(raw.get("changepercent")),
        "amount": _to_float(raw.get("amount")),
        "volume_ratio": 0.0,  # 新浪榜单无量比字段
        "amplitude": round(amplitude, 2),
        "speed": 0.0,  # 新浪榜单无涨速字段
        "turnover": _to_float(raw.get("turnoverratio")),
        "prev_close": settlement,
    }


def fetch_sina_movers_snapshot() -> Dict[str, Dict[str, Any]]:
    """抓取新浪四个排行榜并合并为异动候选快照。"""
    snapshot: Dict[str, Dict[str, Any]] = {}
    failures = 0

    for sort, asc, _label in SINA_RANK_LISTS:
        try:
            rows = _fetch_sina_rank(sort, asc)
            for raw in rows:
                row = _sina_to_row(raw)
                code = row["code"]
                if not code.isdigit():
                    continue
                snapshot.setdefault(code, row)
            time.sleep(0.2)
        except Exception:
            failures += 1

    if failures == len(SINA_RANK_LISTS):
        raise RuntimeError(f"新浪四个榜单请求全部失败 ({SINA_RANK_URL})")

    return snapshot


# ---------------------------------------------------------------------------
# 东方财富榜单通道 (可选，提供量比/涨速)
# ---------------------------------------------------------------------------
CLIST_URL = "https://82.push2.eastmoney.com/api/qt/clist/get"
FS = "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048"
FIELDS = "f2,f3,f6,f7,f8,f10,f12,f14,f18,f22"
EM_RANK_LISTS = [
    ("f3", 1, "涨幅榜"),
    ("f3", 0, "跌幅榜"),
    ("f10", 1, "量比榜"),
    ("f22", 1, "涨速榜"),
    ("f7", 1, "振幅榜"),
    ("f6", 1, "成交额榜"),
]


@retry(max_retries=3, delay=1.0, backoff=2)
def _fetch_em_rank(fid: str, po: int) -> list:
    """拉取东方财富单个排序榜单 (单页 100 条)。"""
    params = {
        "pn": "1", "pz": "100", "po": str(po), "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2", "invt": "2", "fid": fid,
        "fs": FS, "fields": FIELDS,
    }
    for proxies in ({"http": None, "https": None}, None):
        try:
            resp = requests.get(CLIST_URL, params=params, timeout=10, proxies=proxies)
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            return data.get("diff") or []
        except (requests.RequestException, ValueError):
            if proxies is None:
                raise
            continue
    return []


def fetch_eastmoney_movers_snapshot() -> Dict[str, Dict[str, Any]]:
    """抓取东方财富六个榜单并合并为异动候选快照。"""
    snapshot: Dict[str, Dict[str, Any]] = {}
    failures = 0

    for fid, po, _label in EM_RANK_LISTS:
        try:
            rows = _fetch_em_rank(fid, po)
            for raw in rows:
                code = str(raw.get("f12", "")).zfill(6)
                if not code.isdigit():
                    continue
                snapshot.setdefault(code, {
                    "code": code,
                    "name": str(raw.get("f14", code)),
                    "price": _to_float(raw.get("f2")),
                    "pct": _to_float(raw.get("f3")),
                    "amount": _to_float(raw.get("f6")),
                    "volume_ratio": _to_float(raw.get("f10")),
                    "amplitude": _to_float(raw.get("f7")),
                    "speed": _to_float(raw.get("f22")),
                    "turnover": _to_float(raw.get("f8")),
                    "prev_close": _to_float(raw.get("f18")),
                })
            time.sleep(0.2)
        except Exception:
            failures += 1

    if failures == len(EM_RANK_LISTS):
        raise RuntimeError(f"东方财富六个榜单请求全部失败 ({CLIST_URL})")

    return snapshot


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------
FETCHERS = {
    "sina": fetch_sina_movers_snapshot,
    "eastmoney": fetch_eastmoney_movers_snapshot,
}


def fetch_movers_snapshot(data_source: str = "sina") -> Dict[str, Dict[str, Any]]:
    """按数据源抓取异动候选快照；指定通道失败时自动回退另一通道。"""
    primary = FETCHERS.get(data_source)
    if primary is None:
        raise ValueError(f"未知数据源: {data_source} (可选: {', '.join(FETCHERS)})")

    order = [data_source] + [k for k in FETCHERS if k != data_source]
    last_err: Exception | None = None
    for name in order:
        try:
            snapshot = FETCHERS[name]()
            if snapshot:
                return snapshot
        except Exception as e:
            last_err = e
    raise RuntimeError(f"所有数据源均不可用: {last_err}")


def _to_float(value: Any) -> float:
    """'-' / None / 非数字 -> 0.0。"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
