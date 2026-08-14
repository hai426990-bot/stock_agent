"""Tests for the vectorized backtest engine."""
import numpy as np
import pandas as pd
import pytest

from backtest.engine import VectorizedEngine
from backtest.analytics import PerformanceAnalytics


class _AlwaysLongStrategy:
    """Always hold: position = 1 everywhere."""

    params = None

    def generate_signals(self, df):
        return pd.Series(1.0, index=df.index)


class _HalfwayStrategy:
    """Cash for the first half, long for the second half."""

    params = None

    def generate_signals(self, df):
        pos = pd.Series(0.0, index=df.index)
        pos.iloc[len(df) // 2:] = 1.0
        return pos


def _df(n=120):
    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0.1, 1.0, n))
    return pd.DataFrame({
        "dt": idx,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.full(n, 1_000_000),
    })


def test_equity_curve_starts_at_initial_cash():
    engine = VectorizedEngine(initial_cash=250_000.0)
    results = engine.run(_AlwaysLongStrategy(), _df())
    assert results["equity"].iloc[0] == pytest.approx(250_000.0)


def test_signal_shifted_no_lookahead():
    """Day t's position must only affect the return realized after t."""
    df = _df()
    results = VectorizedEngine().run(_HalfwayStrategy(), df)
    first_positive = (results["position"] > 0).idxmax()
    # position turns 1 at the switch day; equity must still equal initial cash
    # that day because the return is earned from the NEXT day onward
    switch_idx = len(df) // 2
    assert results["equity"].iloc[switch_idx] == pytest.approx(100_000.0)


def test_trade_costs_reduce_returns():
    df = _df()
    no_cost = VectorizedEngine(commission=0, slippage=0).run(_HalfwayStrategy(), df)
    with_cost = VectorizedEngine(commission=0.0003, slippage=0.001).run(_HalfwayStrategy(), df)
    assert with_cost["equity"].iloc[-1] < no_cost["equity"].iloc[-1]


def test_metrics_computed_with_initial_cash():
    """calculate_metrics must use the engine's initial_cash, not the hardcoded 100k."""
    df = _df()
    engine = VectorizedEngine(initial_cash=250_000.0)
    results = engine.run(_AlwaysLongStrategy(), df)
    metrics = PerformanceAnalytics.calculate_metrics(results, initial_cash=engine.initial_cash)
    # metrics are rounded to 4 decimals internally
    assert metrics["total_return"] == pytest.approx(
        round(results["equity"].iloc[-1] / 250_000.0 - 1, 4), abs=1e-6
    )
    assert set(metrics) >= {"total_return", "cagr", "sharpe", "max_drawdown", "win_rate"}


def test_extract_trade_signals_detects_buy_sell():
    engine = VectorizedEngine()
    results = engine.run(_HalfwayStrategy(), _df())
    signals = engine.extract_trade_signals(results)
    assert len(signals) == 1
    assert signals[0].signal_type == "BUY"


def test_empty_df_returns_empty():
    engine = VectorizedEngine()
    assert engine.run(_AlwaysLongStrategy(), pd.DataFrame()).empty
    assert engine.extract_trade_signals(pd.DataFrame()) == []
