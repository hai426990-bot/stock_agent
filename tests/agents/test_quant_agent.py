"""Unit tests for the quant agent node.

quant_agent_node is driven end-to-end with a synthetic OHLCV DataFrame and
mocked fetchers/persistence, so no AkShare / network calls happen. Includes a
regression test for the KDJ column-name bug that used to crash every run.
"""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from agents.quant_agent import quant_agent_node


def _synthetic_df(n=300):
    """Deterministic OHLCV frame with an upward drift so strategies trade."""
    rng = np.random.default_rng(42)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = 100 * (1 + np.linspace(0, 0.3, n)) + rng.normal(0, 0.5, n)
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    volume = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({
        "dt": idx, "open": open_, "high": high, "low": low,
        "close": close, "volume": volume, "adj_close": close, "turnover": 1.0,
    })


def _base_state():
    return {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "is_sector": False,
        "sector_type": "",
        "config": {
            "api_key": "test-key",
            "api_base": "https://api.example.com/v1",
            "model_name": "gpt-4o",
            "temperature": 0.5,
            "max_tokens": 4096,
            "thinking_mode": True,
            "backtest_lookback_days": 365,
            "backtest_initial_cash": 100000.0,
            "backtest_commission": 0.0003,
            "backtest_slippage": 0.001,
            "backtest_max_runs": 6,
        },
        "error": "",
        "consecutive_failures": 0,
    }


@pytest.fixture
def mock_quant_deps():
    with patch("backtest.data.DataManager.get_data", return_value=_synthetic_df()), \
         patch("backtest.persistence.BacktestPersistence.save_result") as mock_save, \
         patch("agents.quant_agent._fetch_financials", return_value={"roe": 0.3}), \
         patch("agents.quant_agent._fetch_fund_flow", return_value={"主力净流入": 1000}), \
         patch("agents.quant_agent._fetch_industry_data", return_value={"行业": "白酒"}), \
         patch("agents.quant_agent._fetch_valuation_history", return_value={"latest_pe": 25.0}), \
         patch("agents.quant_agent._fetch_market_sentiment", return_value={"情绪描述": "中性"}):
        yield mock_save


def test_quant_node_runs_backtests_and_builds_candidates(mock_quant_deps):
    """The full node runs strategies and produces ranked candidates."""
    result = quant_agent_node(_base_state())

    assert "error" not in result, result.get("error")

    candidates = result["quant_data"]["backtest_candidates"]
    assert len(candidates) > 0
    assert len(candidates) <= 6  # backtest_max_runs honored

    # Ranked by sharpe, descending
    sharpes = [c["metrics"]["sharpe"] for c in candidates]
    assert sharpes == sorted(sharpes, reverse=True)

    for cand in candidates:
        assert cand["label"]
        assert cand["name"]
        assert cand["params"] is not None
        assert set(cand["metrics"]) >= {"sharpe", "cagr", "max_drawdown", "win_rate"}
        assert "summary" in cand
        # Heavy per-run artifacts were removed from the LLM/frontend payload
        assert "curve" not in cand
        assert "signals" not in cand
        assert "buy_count" not in cand

    # Persistence was invoked per run
    assert mock_quant_deps.call_count == len(candidates)


def test_quant_node_technical_indicators_complete(mock_quant_deps):
    """KDJ/MACD/RSI/BOLL must all be present — regression for the trailing-space
    column name that made `last_row["KDJ_J"]` raise KeyError."""
    result = quant_agent_node(_base_state())

    tech = result["quant_data"]["technical_indicators"]
    assert "latest_price" in tech
    assert set(tech["ma_system"]) == {"ma5", "ma10", "ma20", "ma60"}
    assert set(tech["macd"]) == {"diff", "dea", "hist"}
    assert set(tech["kdj"]) == {"k", "d", "j"}
    assert set(tech["boll"]) == {"upper", "mid", "lower"}
    assert "rsi" in tech
    assert isinstance(tech["patterns"], list)
    # financials / fund flow / sentiment are carried through
    assert result["quant_data"]["financials"]["roe"] == 0.3
    assert result["quant_data"]["market_sentiment"]["情绪描述"] == "中性"


def test_quant_node_insufficient_data_returns_error(mock_quant_deps):
    """Too few rows -> a clear error instead of a crash."""
    with patch("backtest.data.DataManager.get_data", return_value=_synthetic_df(5)):
        result = quant_agent_node(_base_state())
    assert "error" in result
    assert "数据不足" in result["error"]
