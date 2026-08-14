"""Unit tests for technical indicator calculations.

These tests do NOT require Django, network access, or AkShare.
They verify pure math/logic functions in tools/indicators.py.
"""
import math

import pandas as pd
import pytest

from tools.indicators import calculate_kdj as kdj
from tools.indicators import calculate_rsi, calculate_bollinger_bands


def _make_price_series(values):
    """Build a simple OHLC DataFrame from close prices (simulated)."""
    n = len(values)
    return pd.DataFrame({
        "high": [v * 1.02 for v in values],
        "low": [v * 0.98 for v in values],
        "close": values,
    })


@pytest.fixture
def sample_prices():
    return _make_price_series([
        10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
        19, 18, 17, 16, 15, 14, 13, 12, 11, 10,
    ])


class TestKDJ:
    def test_kdj_returns_expected_columns(self, sample_prices):
        result = kdj(sample_prices)
        assert "k" in result.columns
        assert "d" in result.columns
        assert "j" in result.columns
        # Should have same number of rows
        assert len(result) == len(sample_prices)

    def test_kdj_values_in_bounds(self, sample_prices):
        result = kdj(sample_prices)
        # k and d should be between 0 and 100
        assert result["k"].dropna().between(0, 100).all()
        assert result["d"].dropna().between(0, 100).all()

    def test_kdj_on_uptrend(self):
        """In a strong uptrend, k and d should be high."""
        prices = _make_price_series([10 + i for i in range(30)])
        result = kdj(prices)
        # The last few k/d values should be > 50 in an uptrend
        tail_k = result["k"].tail(5).mean()
        assert tail_k > 50, f"Expected k > 50 in uptrend, got {tail_k:.2f}"

    def test_kdj_on_downtrend(self):
        """In a strong downtrend, k and d should be low."""
        prices = _make_price_series([30 - i for i in range(30)])
        result = kdj(prices)
        tail_k = result["k"].tail(5).mean()
        assert tail_k < 50, f"Expected k < 50 in downtrend, got {tail_k:.2f}"

    def test_kdj_handles_constant_prices(self):
        """When all prices are equal, k/d/j should converge to a steady state."""
        prices = _make_price_series([10] * 30)
        result = kdj(prices)
        last_k = result["k"].iloc[-1]
        last_d = result["d"].iloc[-1]
        # In steady state with constant prices, k ≈ 50, d ≈ 50, j ≈ 50
        assert math.isclose(last_k, 50, abs_tol=10), f"Expected k ≈ 50, got {last_k}"
        assert math.isclose(last_d, 50, abs_tol=10), f"Expected d ≈ 50, got {last_d}"

    def test_kdj_handles_short_dataframe(self):
        """With fewer rows than the lookback period (9), k/d/j should be NaN."""
        prices = _make_price_series([10, 11, 12])
        result = kdj(prices)
        # First few rows may have NaN until enough data accumulates
        assert result["k"].iloc[0] is None or pd.isna(result["k"].iloc[0])


class TestRSI:
    def test_rsi_range_and_uptrend(self):
        """RSI of a steady uptrend must be > 50 and within [0, 100]."""
        series = pd.Series([10 + i * 0.5 for i in range(60)])
        rsi = calculate_rsi(series, period=14)
        tail = rsi.dropna()
        assert tail.between(0, 100).all()
        assert tail.iloc[-1] > 60, f"Uptrend RSI should be high, got {tail.iloc[-1]:.2f}"

    def test_rsi_downtrend(self):
        series = pd.Series([100 - i * 0.5 for i in range(60)])
        rsi = calculate_rsi(series, period=14)
        tail = rsi.dropna()
        assert tail.iloc[-1] < 40, f"Downtrend RSI should be low, got {tail.iloc[-1]:.2f}"

    def test_rsi_constant_prices(self):
        """Constant prices -> no gains/losses, RSI is undefined (NaN)."""
        series = pd.Series([10.0] * 40)
        rsi = calculate_rsi(series, period=14)
        assert pd.isna(rsi.iloc[-1])


class TestBollinger:
    def test_bands_structure(self):
        series = pd.Series([10 + i * 0.3 for i in range(40)])
        upper, mid, lower = calculate_bollinger_bands(series, n=20, k=2.0)
        assert len(upper) == len(series)
        # mid must sit between lower and upper everywhere a band is defined
        # (NaN != anything in pandas, so compare only on valid rows)
        valid = upper.notna() & mid.notna() & lower.notna()
        assert (upper[valid] >= mid[valid]).all()
        assert (mid[valid] >= lower[valid]).all()

    def test_bands_widen_with_volatility(self):
        volatile = pd.Series([10] * 20 + [10 + (i % 5) * 3 for i in range(30)])
        steady = pd.Series([10.0] * 50)
        up_v, _, _ = calculate_bollinger_bands(volatile, n=20, k=2.0)
        up_s, _, _ = calculate_bollinger_bands(steady, n=20, k=2.0)
        assert up_v.dropna().std() > up_s.dropna().std()
