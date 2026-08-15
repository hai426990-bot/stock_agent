"""JSON-safe 递归转换工具。

akshare/pandas 返回的数据常含 numpy 标量 (np.float64/np.int64)、Timestamp、
NaN/Inf 等类型。它们能通过 json.dumps（numpy 标量是 float/int 子类），但
LangGraph MemorySaver 的 checkpoint 序列化使用 msgpack (ormsgpack)，对
numpy 类型直接报错；Django JSONField 等也不保证兼容。因此所有进入
AgentState 的数据必须先经 to_json_safe 清洗（前端展示与持久化也因此受益）。
"""
import math
from datetime import datetime
from typing import Any


def to_json_safe(obj: Any) -> Any:
    """递归转换为纯 Python/JSON-safe 值（NaN/Inf -> None，Timestamp -> iso 字符串）。"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]

    # pandas 类型（延迟导入，避免在非 pandas 环境引入依赖）
    try:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            return [to_json_safe(r) for r in obj.to_dict(orient="records")]
        if isinstance(obj, pd.Series):
            return to_json_safe(obj.to_dict())
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    except ImportError:
        pass

    if isinstance(obj, datetime):
        return obj.isoformat()

    # numpy 标量（延迟导入）
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
            return [to_json_safe(v) for v in obj.tolist()]
    except ImportError:
        pass

    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (str, int, bool)):
        return obj
    # 兜底：尝试原生类型；不可序列化的保留原值由调用方处理
    return obj
