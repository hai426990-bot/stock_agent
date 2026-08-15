"""Tests for the backtests API + the quant_agent -> BacktestResult wiring."""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from django.test import Client

from backend.analysis.models import AnalysisReport
from backend.backtests.models import BacktestResult
from backend.backtests.services import record_backtest


def _report():
    return AnalysisReport.objects.create(
        query="600519", stock_code="600519", stock_name="贵州茅台",
        is_sector=False, status=AnalysisReport.Status.COMPLETED,
    )


def _metrics(**overrides):
    m = {
        "sharpe": 1.5, "cagr": 0.25, "max_drawdown": -0.15, "win_rate": 0.55,
        "total_return": 0.3, "trade_count": 12,
    }
    m.update(overrides)
    return m


@pytest.mark.django_db
class TestRecordBacktest:
    def test_record_links_report_and_denormalizes_metrics(self):
        report = _report()
        row = record_backtest(
            str(report.id), "ma_crossover", {"fast": 5, "slow": 20},
            _metrics(), {"symbol": "600519", "rows": 100}, {"initial_cash": 100000.0},
        )
        assert row is not None
        assert row.report_id == report.id
        assert row.strategy_name == "ma_crossover"
        assert row.stock_code == "600519"
        assert row.sharpe == 1.5
        assert row.max_drawdown == -0.15
        assert row.metrics["trade_count"] == 12
        assert row.parameters == {"fast": 5, "slow": 20}
        # JSON-safe for API responses
        detail = row.data_info
        assert detail["rows"] == 100

    def test_record_missing_report_returns_none(self):
        assert record_backtest("00000000-0000-0000-0000-000000000000",
                               "x", {}, _metrics(), {}) is None
        assert record_backtest("not-a-uuid", "x", {}, _metrics(), {}) is None

    def test_quant_agent_wiring_persists_rows(self):
        """quant_agent with report_id in config -> BacktestResult rows exist."""
        report = _report()
        state = {
            "stock_code": "600519", "stock_name": "贵州茅台",
            "is_sector": False, "sector_type": "",
            "config": {
                "api_key": "test-key", "model_name": "gpt-4o",
                "temperature": 0.5, "max_tokens": 4096, "thinking_mode": False,
                "backtest_lookback_days": 365, "backtest_initial_cash": 100000.0,
                "backtest_commission": 0.0003, "backtest_slippage": 0.001,
                "backtest_max_runs": 6, "report_id": str(report.id),
            },
            "error": "", "consecutive_failures": 0,
        }
        rng = np.random.default_rng(42)
        idx = pd.date_range("2025-01-01", periods=300, freq="B")
        close = 100 * (1 + np.linspace(0, 0.3, 300)) + rng.normal(0, 0.5, 300)
        df = pd.DataFrame({
            "dt": idx, "open": close * 0.99, "high": close * 1.01,
            "low": close * 0.98, "close": close, "volume": 2_000_000,
            "adj_close": close, "turnover": 1.0,
        })

        from agents.quant_agent import quant_agent_node
        with patch("backtest.data.DataManager.get_data", return_value=df), \
             patch("backtest.persistence.BacktestPersistence.save_result", return_value=""), \
             patch("agents.quant_agent._fetch_financials", return_value={"roe": 0.3}), \
             patch("agents.quant_agent._fetch_fund_flow", return_value={}), \
             patch("agents.quant_agent._fetch_industry_data", return_value={}), \
             patch("agents.quant_agent._fetch_valuation_history", return_value={}), \
             patch("agents.quant_agent._fetch_market_sentiment", return_value={}):
            result = quant_agent_node(state)

        assert "error" not in result, result.get("error")
        rows = list(BacktestResult.objects.filter(report_id=report.id))
        assert len(rows) == len(result["quant_data"]["backtest_candidates"]) > 0
        assert {r.strategy_name for r in rows} == {c["name"] for c in result["quant_data"]["backtest_candidates"]}
        # every row links to the report and carries metrics
        assert all(r.metrics.get("sharpe") is not None for r in rows)

    def test_quant_agent_without_report_id_skips_db(self):
        """CLI mode (no report_id) must not touch the DB."""
        state = {
            "stock_code": "600519", "stock_name": "贵州茅台",
            "is_sector": False, "sector_type": "",
            "config": {"api_key": "test-key", "model_name": "gpt-4o",
                       "temperature": 0.5, "max_tokens": 4096, "thinking_mode": False,
                       "backtest_lookback_days": 365, "backtest_initial_cash": 100000.0,
                       "backtest_commission": 0.0003, "backtest_slippage": 0.001,
                       "backtest_max_runs": 3},
            "error": "", "consecutive_failures": 0,
        }
        rng = np.random.default_rng(1)
        idx = pd.date_range("2025-01-01", periods=300, freq="B")
        close = 100 * (1 + np.linspace(0, 0.2, 300)) + rng.normal(0, 0.5, 300)
        df = pd.DataFrame({
            "dt": idx, "open": close, "high": close * 1.01, "low": close * 0.99,
            "close": close, "volume": 2_000_000, "adj_close": close, "turnover": 1.0,
        })
        from agents.quant_agent import quant_agent_node
        with patch("backtest.data.DataManager.get_data", return_value=df), \
             patch("backtest.persistence.BacktestPersistence.save_result", return_value=""), \
             patch("agents.quant_agent._fetch_financials", return_value={}), \
             patch("agents.quant_agent._fetch_fund_flow", return_value={}), \
             patch("agents.quant_agent._fetch_industry_data", return_value={}), \
             patch("agents.quant_agent._fetch_valuation_history", return_value={}), \
             patch("agents.quant_agent._fetch_market_sentiment", return_value={}):
            result = quant_agent_node(state)
        assert "error" not in result, result.get("error")
        assert BacktestResult.objects.count() == 0


@pytest.mark.django_db
class TestBacktestsAPI:
    def _seed(self):
        report = _report()
        record_backtest(str(report.id), "ma_crossover", {"fast": 5}, _metrics(sharpe=1.2),
                        {"symbol": "600519"}, {})
        record_backtest(str(report.id), "rsi_reversion", {"period": 14}, _metrics(sharpe=0.8),
                        {"symbol": "600519"}, {})
        record_backtest(None, "macd_trend", {"fast": 12}, _metrics(sharpe=2.1),
                        {"symbol": "000858"}, {})
        return report

    def test_list_paginated(self):
        self._seed()
        resp = Client().get("/api/backtests/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        item = data["items"][0]
        assert {"id", "run_id", "strategy_name", "stock_code", "sharpe",
                "cagr", "max_drawdown", "win_rate", "report_id", "timestamp"} <= set(item)

    def test_list_filters(self):
        self._seed()
        resp = Client().get("/api/backtests/?stock_code=600519&strategy_name=ma_crossover")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["strategy_name"] == "ma_crossover"

    def test_list_filter_by_report(self):
        report = self._seed()
        resp = Client().get(f"/api/backtests/?report_id={report.id}")
        data = resp.json()
        assert data["total"] == 2
        assert all(i["report_id"] == str(report.id) for i in data["items"])

    def test_detail_returns_json_blobs(self):
        self._seed()
        run_id = BacktestResult.objects.get(strategy_name="ma_crossover").run_id
        resp = Client().get(f"/api/backtests/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parameters"] == {"fast": 5}
        assert data["metrics"]["sharpe"] == 1.2
        assert data["engine"] == {}

    def test_detail_missing_returns_404(self):
        resp = Client().get("/api/backtests/nonexistent-run")
        assert resp.status_code == 404

    def test_delete(self):
        self._seed()
        run_id = BacktestResult.objects.get(strategy_name="macd_trend").run_id
        resp = Client().delete(f"/api/backtests/{run_id}")
        assert resp.status_code == 200
        assert BacktestResult.objects.count() == 2
        resp = Client().get(f"/api/backtests/{run_id}")
        assert resp.status_code == 404
