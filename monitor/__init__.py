"""
盘中异动监控循环代理 (Loop Agent)

开盘到收盘期间以固定间隔轮询全市场实时行情，
对盘中出现的异动（急涨急跌、量比异常、封板/炸板、指数急变等）
及时做规则检测 + LLM 分析判断。

模块划分:
    - session:   A股交易时段判断 (9:30-11:30, 13:00-15:00, 工作日)
    - fetcher:   异动候选快照抓取 (新浪/东方财富榜单 Top100, 自动回退)
    - detector:  异动检测器 (快照构建 / 相邻快照差值 / 规则打分)
    - analyzer:  异动分析 Agent (LLM 结合新闻/资金流/技术面给出判断)
    - loop:      循环调度器 (轮询、冷却去重、事件落盘、收盘总结)
"""

from monitor.session import is_trading_time, is_trading_day, next_session_info

__all__ = ["is_trading_time", "is_trading_day", "next_session_info"]
