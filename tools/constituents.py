from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


def _first_present(d: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return None


def parse_constituent_item(item: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """
    Best-effort parse of an AkShare board constituent row into (code, name, weight).
    Keys vary across endpoints / versions, so we try a few common variants.
    """
    raw_code = _first_present(
        item,
        [
            "代码",
            "股票代码",
            "证券代码",
            "symbol",
            "ts_code",
            "code",
        ],
    )
    raw_name = _first_present(
        item,
        [
            "名称",
            "股票名称",
            "证券简称",
            "name",
        ],
    )
    raw_weight = _first_present(
        item,
        [
            "权重",
            "权重(%)",
            "占比",
            "weight",
        ],
    )

    code = None if raw_code is None else str(raw_code).strip()
    name = None if raw_name is None else str(raw_name).strip()

    weight: Optional[float] = None
    if raw_weight is not None:
        try:
            weight = float(str(raw_weight).strip().replace("%", ""))
        except Exception:
            weight = None

    if code and code.lower().startswith(("sh", "sz")) and len(code) >= 8:
        code = code[-6:]

    return code, name, weight


def top_constituents(sector_cons: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Return top N constituents in the given order, with normalized code/name/weight.
    """
    if not sector_cons or top_n <= 0:
        return []
    selected = []
    for row in sector_cons[:top_n]:
        code, name, weight = parse_constituent_item(row)
        selected.append({"code": code, "name": name, "weight": weight, "raw": row})
    return selected

