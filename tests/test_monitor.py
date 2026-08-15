"""Unit tests for the intraday anomaly monitor (monitor package).

These tests do NOT require network access, AkShare, or LLM.
They verify pure logic: trading session math, snapshot building,
anomaly detection rules, and rule-based fallback judgment.
"""
from datetime import datetime

import pandas as pd
import pytest

from monitor import session
from monitor.analyzer import rule_based_judgment
from monitor.detector import (
    build_snapshot,
    detect_anomalies,
    detect_index_anomalies,
    limit_pct,
)


# ---------------------------------------------------------------------------
# 交易时段判断
# ---------------------------------------------------------------------------
class TestTradingSession:
    def test_weekday_morning_is_trading_time(self):
        dt = datetime(2026, 8, 17, 10, 0)  # 周一
        assert session.is_trading_day(dt)
        assert session.is_trading_time(dt)

    def test_weekend_not_trading(self):
        dt = datetime(2026, 8, 16, 10, 0)  # 周日
        assert not session.is_trading_day(dt)
        assert not session.is_trading_time(dt)

    def test_morning_and_afternoon_sessions(self):
        assert session.is_trading_time(datetime(2026, 8, 17, 9, 30))
        assert session.is_trading_time(datetime(2026, 8, 17, 11, 30))
        assert session.is_trading_time(datetime(2026, 8, 17, 13, 0))
        assert session.is_trading_time(datetime(2026, 8, 17, 15, 0))

    def test_lunch_break_not_trading(self):
        assert not session.is_trading_time(datetime(2026, 8, 17, 11, 31))
        assert not session.is_trading_time(datetime(2026, 8, 17, 12, 59))

    def test_outside_hours_not_trading(self):
        assert not session.is_trading_time(datetime(2026, 8, 17, 9, 29))
        assert not session.is_trading_time(datetime(2026, 8, 17, 15, 1))

    def test_next_session_info_weekend(self):
        # 周六 -> 下周一 09:30
        in_watch, nxt, desc = session.next_session_info(datetime(2026, 8, 15, 10, 0))
        assert not in_watch
        assert nxt == datetime(2026, 8, 17, 9, 30)
        assert "非交易日" in desc

    def test_next_session_info_after_close(self):
        # 周五收盘后 -> 下周一 09:30
        in_watch, nxt, desc = session.next_session_info(datetime(2026, 8, 14, 15, 30))
        assert in_watch
        assert nxt == datetime(2026, 8, 17, 9, 30)
        assert "已收盘" in desc

    def test_next_session_info_lunch_break(self):
        in_watch, nxt, desc = session.next_session_info(datetime(2026, 8, 17, 12, 0))
        assert in_watch
        assert nxt == datetime(2026, 8, 17, 13, 0)
        assert "午间" in desc


# ---------------------------------------------------------------------------
# 涨跌停幅度按板块
# ---------------------------------------------------------------------------
class TestLimitPct:
    def test_main_board(self):
        assert limit_pct("600519") == 9.8
        assert limit_pct("000001") == 9.8

    def test_st_board(self):
        assert limit_pct("600001", "ST某某") == 4.8
        assert limit_pct("000002", "*ST某某") == 4.8

    def test_growth_and_star_board(self):
        assert limit_pct("300750") == 19.8
        assert limit_pct("688981") == 19.8

    def test_bse_board(self):
        assert limit_pct("830799") == 29.8


# ---------------------------------------------------------------------------
# 快照构建
# ---------------------------------------------------------------------------
def _make_spot_df(rows):
    """构造模拟的东方财富全市场行情 DataFrame。"""
    return pd.DataFrame(rows)


class TestBuildSnapshot:
    def test_normal_rows(self):
        df = _make_spot_df([
            {"代码": "600519", "名称": "贵州茅台", "最新价": 1500.0, "涨跌幅": 2.5,
             "成交额": 5e9, "量比": 1.2, "振幅": 3.0, "涨速": 0.1, "换手率": 0.5, "昨收": 1463.4},
        ])
        snap = build_snapshot(df)
        assert "600519" in snap
        row = snap["600519"]
        assert row["name"] == "贵州茅台"
        assert row["pct"] == 2.5
        assert row["volume_ratio"] == 1.2

    def test_missing_optional_columns_default_to_zero(self):
        df = _make_spot_df([
            {"代码": "000001", "名称": "平安银行", "最新价": 12.0, "涨跌幅": 0.5},
        ])
        snap = build_snapshot(df)
        assert snap["000001"]["volume_ratio"] == 0.0
        assert snap["000001"]["amount"] == 0.0

    def test_nan_values_handled(self):
        df = _make_spot_df([
            {"代码": "600000", "名称": "浦发银行", "最新价": 10.0, "涨跌幅": float("nan"),
             "成交额": None, "量比": 1.0, "振幅": 2.0, "涨速": 0.0, "换手率": 0.1, "昨收": 9.9},
        ])
        snap = build_snapshot(df)
        assert snap["600000"]["pct"] == 0.0

    def test_empty_df(self):
        assert build_snapshot(pd.DataFrame()) == {}
        assert build_snapshot(None) == {}


# ---------------------------------------------------------------------------
# 异动检测
# ---------------------------------------------------------------------------
def _snapshot_row(code, name, pct, volume_ratio=1.0, amplitude=3.0,
                  speed=0.0, amount=1e8, turnover=2.0):
    return {
        "code": code, "name": name, "price": 10.0, "pct": pct,
        "amount": amount, "volume_ratio": volume_ratio, "amplitude": amplitude,
        "speed": speed, "turnover": turnover, "prev_close": 9.5,
    }


class TestDetectAnomalies:
    def test_surge_and_plunge(self):
        snap = {
            "600001": _snapshot_row("600001", "涨股", pct=8.0),
            "600002": _snapshot_row("600002", "跌股", pct=-8.0),
            "600003": _snapshot_row("600003", "平淡", pct=1.0),
        }
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap)}
        assert ("600001", "surge") in signals
        assert ("600002", "plunge") in signals
        assert ("600003", "surge") not in signals

    def test_volume_surge(self):
        snap = {"600001": _snapshot_row("600001", "放量", pct=1.0, volume_ratio=6.0)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap)}
        assert ("600001", "volume_surge") in signals

    def test_turnover_surge(self):
        snap = {"600001": _snapshot_row("600001", "高换手", pct=3.0,
                                        volume_ratio=0.0, turnover=18.0)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap)}
        assert ("600001", "turnover_surge") in signals

    def test_amplitude_anomaly(self):
        snap = {"600001": _snapshot_row("600001", "宽幅", pct=2.0, amplitude=15.0)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap)}
        assert ("600001", "amplitude") in signals

    def test_new_limit_up_delta(self):
        prev = {"600001": _snapshot_row("600001", "封板", pct=5.0)}
        snap = {"600001": _snapshot_row("600001", "封板", pct=10.0)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap, prev)}
        assert ("600001", "limit_up_new") in signals

    def test_unseal_delta(self):
        prev = {"600001": _snapshot_row("600001", "炸板", pct=10.0)}
        snap = {"600001": _snapshot_row("600001", "炸板", pct=7.0)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap, prev)}
        assert ("600001", "unseal") in signals

    def test_growth_board_20pct_limit(self):
        # 创业板 20% 涨停: 18% 不触发新封板, 20% 触发
        prev = {"300001": _snapshot_row("300001", "创业股", pct=10.0)}
        snap_ok = {"300001": _snapshot_row("300001", "创业股", pct=18.0)}
        snap_limit = {"300001": _snapshot_row("300001", "创业股", pct=20.0)}
        signals_ok = {(a["code"], a["signal"]) for a in detect_anomalies(snap_ok, prev)}
        assert ("300001", "limit_up_new") not in signals_ok
        signals_limit = {(a["code"], a["signal"]) for a in detect_anomalies(snap_limit, prev)}
        assert ("300001", "limit_up_new") in signals_limit

    def test_no_prev_snapshot_no_delta_signals(self):
        snap = {"600001": _snapshot_row("600001", "封板", pct=10.0)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap, None)}
        assert ("600001", "surge") in signals
        assert ("600001", "limit_up_new") not in signals

    def test_sorted_by_score_desc(self):
        snap = {
            "600001": _snapshot_row("600001", "小涨", pct=7.0),
            "600002": _snapshot_row("600002", "大涨", pct=9.5, amount=1e9),
        }
        anomalies = detect_anomalies(snap)
        scores = [a["score"] for a in anomalies]
        assert scores == sorted(scores, reverse=True)
        assert anomalies[0]["code"] == "600002"

    def test_custom_thresholds(self):
        cfg = {"surge_pct": 3.0, "plunge_pct": -3.0}
        snap = {"600001": _snapshot_row("600001", "小涨", pct=3.5)}
        signals = {(a["code"], a["signal"]) for a in detect_anomalies(snap, config=cfg)}
        assert ("600001", "surge") in signals


class TestDetectIndexAnomalies:
    def test_large_move_detected(self):
        indices = [
            {"name": "上证指数", "price": 3200.0, "change": 32.0, "change_pct": 1.5},
            {"name": "深证成指", "price": 10000.0, "change": 50.0, "change_pct": 0.5},
        ]
        result = detect_index_anomalies(indices)
        assert len(result) == 1
        assert result[0]["name"] == "上证指数"
        assert result[0]["signal"] == "index_anomaly"

    def test_custom_threshold(self):
        indices = [
            {"name": "上证指数", "price": 3200.0, "change": 20.0, "change_pct": 0.6},
        ]
        assert detect_index_anomalies(indices, {"index_pct": 0.5}) != []
        assert detect_index_anomalies(indices, {"index_pct": 1.0}) == []


# ---------------------------------------------------------------------------
# 规则化降级判断
# ---------------------------------------------------------------------------
class TestRuleBasedJudgment:
    def test_returns_required_fields(self):
        anomaly = {"code": "600519", "name": "贵州茅台", "signal_label": "急涨",
                   "pct": 8.0, "volume_ratio": 3.0, "amount": 1e9}
        result = rule_based_judgment(anomaly)
        assert result["judgment"]
        assert result["risk_level"] in ("高", "中", "低")
        assert isinstance(result["watch_points"], list)
        assert len(result["watch_points"]) > 0

    def test_limit_move_is_high_risk(self):
        anomaly = {"code": "600519", "name": "贵州茅台", "signal_label": "新封板",
                   "pct": 10.0, "volume_ratio": 1.0, "amount": 1e8}
        assert rule_based_judgment(anomaly)["risk_level"] == "高"

    def test_small_move_is_low_risk(self):
        anomaly = {"code": "600519", "name": "贵州茅台", "signal_label": "振幅异动",
                   "pct": 2.0, "volume_ratio": 1.0, "amount": 1e8}
        assert rule_based_judgment(anomaly)["risk_level"] == "低"
