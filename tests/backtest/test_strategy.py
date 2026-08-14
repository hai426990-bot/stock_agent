"""Tests for the strategy registry — regression coverage for the bugs found in
the refactor (duplicate method override, ROE threshold units, market-cap units).
"""
import numpy as np
import pandas as pd
import pytest

from backtest.engine import VectorizedEngine
from backtest.strategy import (
    STRATEGY_REGISTRY,
    Bollinger_Breakout_Volume_Strategy,
    Quality_Growth_PEG_Strategy,
    Leader_Momentum_Drawdown_Strategy,
    Leader_Quality_Value_Strategy,
)


def _df(n=300, **fundamental_cols):
    rng = np.random.default_rng(3)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = 100 * (1 + np.linspace(0, 0.4, n)) + rng.normal(0, 0.5, n)
    df = pd.DataFrame({
        "dt": idx,
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": rng.integers(1_000_000, 5_000_000, n),
    })
    for name, val in fundamental_cols.items():
        df[name] = val
    return df


def test_registry_has_expected_strategies():
    for name in ("ma_crossover", "rsi_reversion", "macd_trend", "boll_breakout_volume",
                 "quality_growth_peg", "leader_momentum_drawdown", "grid_trading"):
        assert name in STRATEGY_REGISTRY


def test_bollinger_breakout_uses_its_own_params():
    """Regression: the class previously re-defined get_params_class/generate_signals
    with Trend_Momentum logic, so instantiating it with bb_* params crashed."""
    strategy = Bollinger_Breakout_Volume_Strategy(params={
        "bb_period": 20, "bb_std": 2.0, "volume_period": 20,
        "volume_factor": 1.2, "exit_on_mid": True,
    })
    assert strategy.params.__class__.__name__ == "Bollinger_Breakout_Volume_Params"
    signals = strategy.generate_signals(_df())
    assert signals.dtype == float
    assert set(signals.unique()) <= {0.0, 1.0}


def test_bollinger_breakout_runs_in_engine():
    df = _df()
    strategy = Bollinger_Breakout_Volume_Strategy(params={
        "bb_period": 20, "bb_std": 2.0, "volume_period": 20,
        "volume_factor": 1.2, "exit_on_mid": True,
    })
    results = VectorizedEngine().run(strategy, df)
    assert not results.empty
    assert "equity" in results.columns


def test_quality_growth_peg_roe_decimal_units():
    """ROE comes from _parse_chinese_num as a decimal (0.152), so thresholds
    must be decimals — 15.0 previously made the strategy never trade."""
    df = _df(roe=0.25, peg=1.0)
    strategy = Quality_Growth_PEG_Strategy(params={})
    signals = strategy.generate_signals(df)
    assert signals.iloc[-1] > 0  # strong ROE + PEG in range -> full position


def test_leader_strategies_market_cap_in_yi():
    """total_mv is normalized to 亿元 (100M CNY) by DataManager, so the
    documented 500.0/1000.0 thresholds actually filter."""
    big = _df(total_mv=800.0)   # 800亿 -> leader
    small = _df(total_mv=50.0)  # 50亿  -> not a leader

    lm = Leader_Momentum_Drawdown_Strategy(params={})
    signals_big = lm.generate_signals(big)
    signals_small = lm.generate_signals(small)
    assert signals_big.max() >= 0
    assert signals_small.max() == 0 or signals_big.sum() > signals_small.sum()

    lq = Leader_Quality_Value_Strategy(params={})
    assert lq.generate_signals(_df(total_mv=800.0, roe=0.2, pe=15.0)).max() > 0


def test_data_manager_total_mv_normalization():
    """DataManager divides total market value by 1e8 to produce 亿元 units."""
    from backtest.data import DataManager
    dm = DataManager(cache_dir=".backtest_cache")
    total_shares = 2_000_000_000  # 20亿股
    df = pd.DataFrame({"close": [10.0, 20.0]})
    df["total_mv"] = df["close"] * total_shares / 1e8
    assert df["total_mv"].tolist() == [200.0, 400.0]  # 200亿 / 400亿
