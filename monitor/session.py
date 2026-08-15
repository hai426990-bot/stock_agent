"""
A股交易时段判断

规则:
    - 交易日: 周一至周五 (法定节假日由上层数据可用性兜底, 此处不做节假日表)
    - 上午时段: 09:30 - 11:30 (含开盘集合竞价后的连续竞价)
    - 下午时段: 13:00 - 15:00
    - 盘中监控区间 [open, close]: 09:15 开盘集合竞价开始即进入等待, 15:00 收盘结束

时区: 所有判断基于本地时间 (Windows/国内部署均为东八区)。
"""
from datetime import datetime, time, timedelta
from typing import Tuple, Optional

# 交易日时段边界
MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)

# 监控窗口(含集合竞价与午间暂停): 用于决定"是否需要进入循环等待"
WATCH_START = time(9, 15)
WATCH_END = time(15, 5)


def is_trading_day(dt: Optional[datetime] = None) -> bool:
    """是否工作日 (周一至周五)。"""
    dt = dt or datetime.now()
    return dt.weekday() < 5


def is_trading_time(dt: Optional[datetime] = None) -> bool:
    """当前是否处于连续竞价交易时段 (9:30-11:30 或 13:00-15:00)。"""
    dt = dt or datetime.now()
    if not is_trading_day(dt):
        return False
    t = dt.time()
    return (MORNING_OPEN <= t <= MORNING_CLOSE) or (AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE)


def in_watch_window(dt: Optional[datetime] = None) -> bool:
    """当前是否处于监控窗口 (9:15-15:05, 工作日)。

    循环调度器用该函数决定是否进入等待: 开盘前等待开盘、午间等待复盘、
    收盘后结束循环。区别于 is_trading_time (仅连续竞价时段)。
    """
    dt = dt or datetime.now()
    if not is_trading_day(dt):
        return False
    return WATCH_START <= dt.time() <= WATCH_END


def next_session_info(dt: Optional[datetime] = None) -> Tuple[bool, Optional[datetime], Optional[str]]:
    """计算下一个关键时点。

    Returns:
        (是否在工作日监控窗口内, 下一个动作时点, 动作描述):
        - 盘中: (True, None, "trading")
        - 午间休市: (True, 13:00, "午间休市, 等待下午开盘")
        - 盘前: (True, 当日 09:30, "等待开盘")
        - 盘后: (True, 次日 09:30, "已收盘")
        - 非工作日: (False, 下一工作日 09:30, "非交易日")
    """
    dt = dt or datetime.now()
    if not is_trading_day(dt):
        # 找到下一个工作日
        days_ahead = 1
        nxt = dt + timedelta(days=days_ahead)
        while nxt.weekday() >= 5:
            days_ahead += 1
            nxt = dt + timedelta(days=days_ahead)
        nxt = nxt.replace(hour=9, minute=30, second=0, microsecond=0)
        return False, nxt, "非交易日, 等待下一交易日开盘"

    t = dt.time()
    if t < WATCH_START:
        nxt = dt.replace(hour=9, minute=30, second=0, microsecond=0)
        return True, nxt, "等待开盘"
    if t <= MORNING_CLOSE:
        return True, None, "trading"
    if t < AFTERNOON_OPEN:
        nxt = dt.replace(hour=13, minute=0, second=0, microsecond=0)
        return True, nxt, "午间休市, 等待下午开盘"
    if t <= AFTERNOON_CLOSE:
        return True, None, "trading"
    # 收盘后
    days_ahead = 1
    nxt = dt + timedelta(days=days_ahead)
    while nxt.weekday() >= 5:
        days_ahead += 1
        nxt = dt + timedelta(days=days_ahead)
    nxt = nxt.replace(hour=9, minute=30, second=0, microsecond=0)
    return True, nxt, "已收盘"
