"""
盘中异动检测器

以全市场实时快照 (ak.stock_zh_a_spot_em) 为输入，规则化识别异动信号:

    单快照信号 (无需历史):
        surge           急涨        涨跌幅 >= surge_pct 或 涨速 >= surge_speed
        plunge          急跌        涨跌幅 <= -plunge_pct
        volume_surge    放量异动    量比 >= volume_ratio (仅东方财富数据源)
        turnover_surge  高换手异动  换手率 >= turnover_pct (新浪数据源补充)
        amplitude       振幅异动    振幅 >= amplitude_pct

    相邻快照差值信号 (需要上一次快照):
        limit_up_new    新封板      上一快照未涨停 -> 本快照涨停
        limit_down_new  新跌停      上一快照未跌停 -> 本快照跌停
        unseal          炸板        上一快照涨停 -> 本快照跌破涨停价

每条信号按强度打分 (0-100)，供调度器排序后优先分析。
检测逻辑保持纯函数，便于单元测试；网络与轮询由 loop 层负责。
"""
from typing import Any, Dict, List, Optional

import pandas as pd

# 默认检测阈值
DEFAULT_CONFIG: Dict[str, float] = {
    "surge_pct": 7.0,          # 单日涨幅触发急涨
    "plunge_pct": -7.0,        # 单日跌幅触发急跌
    "surge_speed": 3.0,        # 涨速(每分钟涨跌%)触发急拉
    "volume_ratio": 5.0,       # 量比触发放量异动
    "turnover_pct": 15.0,      # 换手率(%)触发高换手异动
    "amplitude_pct": 12.0,     # 振幅触发振幅异动
    "limit_margin": 0.3,       # 距涨跌停价差容忍度(%)，用于炸板/封板判定
    "index_pct": 1.0,          # 指数单日涨跌幅触发指数异动
}

# 涨跌停幅度按板块区分 (%)
_BOARD_LIMIT = [
    (("ST", "st"), 4.8),            # ST 股 ±5%
    (("300", "301", "302"), 19.8),  # 创业板 ±20%
    (("688", "689"), 19.8),         # 科创板 ±20%
    (("8", "4", "92"), 29.8),       # 北交所 ±30%
]
_MAIN_BOARD_LIMIT = 9.8             # 沪深主板 ±10%


def limit_pct(code: str, name: str = "") -> float:
    """返回该股票的单日涨跌停幅度阈值 (%)。"""
    for prefixes, pct in _BOARD_LIMIT:
        if code.startswith(prefixes) or any(k in name for k in prefixes):
            return pct
    return _MAIN_BOARD_LIMIT


def _f(df: pd.DataFrame, row_idx: int, col: str) -> float:
    """安全读取 DataFrame 单元格并转 float，缺列/NaN 返回 0。"""
    if col not in df.columns:
        return 0.0
    try:
        val = df.iloc[row_idx][col]
    except (IndexError, KeyError):
        return 0.0
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def build_snapshot(spot_df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """从东方财富全市场实时行情 DataFrame 构建快照 (代码 -> 标准化字段)。

    Args:
        spot_df: ak.stock_zh_a_spot_em() 返回的 DataFrame

    Returns:
        以股票代码为键的快照字典:
            {code: {code, name, price, pct, amount, volume_ratio,
                    amplitude, speed, turnover, prev_close}}
    """
    if spot_df is None or spot_df.empty:
        return {}

    code_col = next((c for c in spot_df.columns if "代码" in c), "代码")
    name_col = next((c for c in spot_df.columns if "名称" in c), "名称")

    snapshot: Dict[str, Dict[str, Any]] = {}
    for i in range(len(spot_df)):
        try:
            code = str(spot_df.iloc[i][code_col]).zfill(6)
            name = str(spot_df.iloc[i][name_col])
        except (KeyError, ValueError):
            continue
        if not code.isdigit():
            continue
        snapshot[code] = {
            "code": code,
            "name": name,
            "price": _f(spot_df, i, "最新价"),
            "pct": _f(spot_df, i, "涨跌幅"),
            "amount": _f(spot_df, i, "成交额"),
            "volume_ratio": _f(spot_df, i, "量比"),
            "amplitude": _f(spot_df, i, "振幅"),
            "speed": _f(spot_df, i, "涨速"),
            "turnover": _f(spot_df, i, "换手率"),
            "prev_close": _f(spot_df, i, "昨收"),
        }
    return snapshot


def _score(anomaly: Dict[str, Any]) -> float:
    """按异动强度打分 (0-100)，用于排序。

    基础分来自涨跌幅幅度，量比与成交额作为加权加成。
    """
    pct = abs(anomaly.get("pct", 0.0))
    base = min(100.0, pct / 10.0 * 100.0)          # 10% 幅度即满分
    bonus = 0.0
    if anomaly.get("volume_ratio", 0.0) >= 5:
        bonus += 10.0
    if anomaly.get("amount", 0.0) >= 5e8:          # 成交额 >= 5 亿
        bonus += 10.0
    if anomaly.get("signal") in ("limit_up_new", "limit_down_new"):
        base = max(base, 90.0)
    if anomaly.get("signal") == "unseal":
        base = max(base, 80.0)
    return round(min(100.0, base + bonus), 1)


def _make_anomaly(snapshot: Dict[str, Any], signal: str, signal_label: str,
                  prev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    item = {
        "code": snapshot["code"],
        "name": snapshot["name"],
        "signal": signal,
        "signal_label": signal_label,
        "price": snapshot["price"],
        "pct": snapshot["pct"],
        "amount": snapshot["amount"],
        "volume_ratio": snapshot["volume_ratio"],
        "turnover": snapshot["turnover"],
        "amplitude": snapshot["amplitude"],
        "speed": snapshot["speed"],
    }
    if prev:
        item["prev_pct"] = prev.get("pct", 0.0)
    item["score"] = _score(item)
    return item


def detect_anomalies(snapshot: Dict[str, Dict[str, Any]],
                     prev_snapshot: Optional[Dict[str, Dict[str, Any]]] = None,
                     config: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """对单个全市场快照检测异动。

    Args:
        snapshot: build_snapshot 的输出
        prev_snapshot: 上一次快照，用于差值信号；首次扫描传 None
        config: 阈值覆盖 (见 DEFAULT_CONFIG)

    Returns:
        按强度降序排列的异动事件列表
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    anomalies: List[Dict[str, Any]] = []

    for code, row in snapshot.items():
        pct = row["pct"]
        limit = limit_pct(code, row["name"])
        is_limit_up = pct >= limit - cfg["limit_margin"]
        is_limit_down = pct <= -(limit - cfg["limit_margin"])

        # --- 单快照信号 ---
        if pct >= cfg["surge_pct"]:
            anomalies.append(_make_anomaly(row, "surge", "急涨"))
        if pct <= cfg["plunge_pct"]:
            anomalies.append(_make_anomaly(row, "plunge", "急跌"))
        if row["volume_ratio"] >= cfg["volume_ratio"]:
            anomalies.append(_make_anomaly(row, "volume_surge", "放量异动"))
        if row["turnover"] >= cfg["turnover_pct"]:
            anomalies.append(_make_anomaly(row, "turnover_surge", "高换手异动"))
        if row["amplitude"] >= cfg["amplitude_pct"]:
            anomalies.append(_make_anomaly(row, "amplitude", "振幅异动"))

        # --- 差值信号 (新封板 / 新跌停 / 炸板) ---
        if prev_snapshot is not None:
            prev = prev_snapshot.get(code)
            if prev is None:
                continue
            prev_limit_up = prev["pct"] >= limit - cfg["limit_margin"]
            prev_limit_down = prev["pct"] <= -(limit - cfg["limit_margin"])
            if is_limit_up and not prev_limit_up:
                anomalies.append(_make_anomaly(row, "limit_up_new", "新封板", prev))
            elif is_limit_down and not prev_limit_down:
                anomalies.append(_make_anomaly(row, "limit_down_new", "新跌停", prev))
            elif prev_limit_up and not is_limit_up:
                anomalies.append(_make_anomaly(row, "unseal", "炸板", prev))

    # 强度降序，稳定排序
    anomalies.sort(key=lambda a: (a["score"], a["pct"]), reverse=True)
    return anomalies


def detect_index_anomalies(indices: List[Dict[str, Any]],
                           config: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """检测指数级异动 (上证/深证/创业板/科创50 单日涨跌幅超阈值)。

    Args:
        indices: get_market_indices() 输出 [{name, price, change, change_pct}]

    Returns:
        异动指数列表，按涨跌幅绝对值降序
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    result = []
    for idx in indices or []:
        pct = idx.get("change_pct")
        if pct is None:
            continue
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        if abs(pct) >= cfg["index_pct"]:
            result.append({
                "code": idx.get("name", "指数"),
                "name": idx.get("name", "指数"),
                "signal": "index_anomaly",
                "signal_label": "指数异动",
                "price": idx.get("price"),
                "pct": pct,
                "score": round(min(100.0, abs(pct) / 2.0 * 100.0), 1),
            })
    result.sort(key=lambda a: abs(a["pct"]), reverse=True)
    return result
