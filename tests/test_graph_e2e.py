"""End-to-end tests for the REAL compiled LangGraph (graph.py + all agents).

Why this file exists: the orchestrator tests use a FakeApp and therefore cannot
catch schema-level bugs. LangGraph **silently drops** node-returned keys that
are not declared in AgentState (verified on langgraph 1.2.6), which previously
made telegraph_analysis / news_parse_success dead data. These tests drive the
real graph with a fake LLM + mocked data fetchers and pin that behavior:

  - B1: telegraph analysis flows into the state and into the strategy report
  - B2: news parse failure degrades the report via news_parse_success
  - revision loop: risk rejection -> strategy regenerates -> risk passes
  - telegraph outage must NOT block/fail the pipeline
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
from contextlib import contextmanager

from pydantic import Field
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from graph import create_alpha_flow_graph


# ---------------------------------------------------------------------------
# Fake LLM: dispatches canned responses by prompt-content markers
# ---------------------------------------------------------------------------

class FakeChatModel(BaseChatModel):
    """BaseChatModel whose _generate dispatches on the prompt text.

    handlers: list of (marker, fn(text) -> str); the first matching marker
    wins, the empty-string marker acts as the strategy fallback (must be last).
    """

    handlers: list = Field(default_factory=list)
    prompts: list = Field(default_factory=list)

    def __init__(self, handlers):
        super().__init__()
        self.handlers = list(handlers)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        text = "\n".join(str(getattr(m, "content", "")) for m in messages)
        self.prompts.append(text)
        for marker, fn in self.handlers:
            if marker in text:
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=fn(text)))]
                )
        raise AssertionError(f"No fake-LLM handler matched prompt: {text[:300]}")

    @property
    def _llm_type(self):
        return "fake-chat-model"


class RiskCounter:
    """Risk verdicts: reject N times, then pass."""

    def __init__(self, rejections=0):
        self.rejections = rejections
        self.calls = 0

    def __call__(self, text):
        self.calls += 1
        if self.calls <= self.rejections:
            return '{"decision": "驳回", "reason": "逻辑矛盾，数据与结论不一致"}'
        return '{"decision": "通过", "reason": "逻辑自洽，风险提示充分"}'


class StrategyCounter:
    """Strategy report that echoes markers for wiring assertions."""

    def __init__(self):
        self.calls = 0

    def __call__(self, text):
        self.calls += 1
        parts = [f"# 投资建议报告（第{self.calls}次生成）", "## 一、核心评级\n买入"]
        if "电报实时动态" in text and "政策利好行业" in text:
            parts.append("电报联动已验证")
        if "资讯维度无法评估" in text:
            parts.append("资讯降级已验证")
        if "修正请求" in text:
            parts.append("已回应修正请求")
        return "\n".join(parts)


def _news_json_handler(text):
    return (
        '{"analysis": "业绩超预期，行业景气度持续提升，机构上调盈利预测，'
        '估值处于合理区间，中短期预期差偏正面", "sentiment_score": 0.6, '
        '"fear_greed_index": 70}'
    )


def _news_garbage_handler(text):
    return "这不是JSON"


def _telegraph_json_handler(text):
    return (
        '{"event_type": "政策", "impact": "正面", "sentiment": "乐观", '
        '"comment": "政策利好行业，关注龙头公司", "opportunities": ["关注龙头"], '
        '"risks": ["短期波动"]}'
    )


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

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


def _agent_config():
    return {
        "api_key": "test-key",
        "api_base": "https://api.example.com/v1",
        "model_name": "gpt-4o",
        "temperature": 0.5,
        "max_tokens": 4096,
        "thinking_mode": False,
        "backtest_lookback_days": 365,
        "backtest_initial_cash": 100000.0,
        "backtest_sector_days": 252,
        "backtest_commission": 0.0003,
        "backtest_slippage": 0.001,
        "backtest_max_runs": 6,
        "news_rss_urls": "",
        "news_enable_reddit": False,
        "news_enable_x": False,
        "news_rss_limit": 12,
        "news_reddit_limit": 12,
        "news_x_limit": 12,
    }


def _initial_state():
    return {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "is_sector": False,
        "sector_type": "",
        "sector_cons": [],
        "news_items": [],
        "news_analysis": "",
        "news_parse_success": True,
        "sentiment_score": 0.0,
        "fear_greed_index": 0.0,
        "telegraph_news": [],
        "telegraph_analysis": {},
        "quant_data": {},
        "technical_indicators": {},
        "strategy_report": "",
        "risk_assessment": {},
        "messages": [],
        "revision_needed": False,
        "count": 0,
        "reasoning_content": [],
        "config": _agent_config(),
        "error": "",
        "consecutive_failures": 0,
    }


@contextmanager
def _patched_env(fake_llm, telegraph_news=None, news_items=None):
    """Mock every network/LLM dependency the real graph touches."""
    news_items = news_items or [
        {"time": "2026-01-01 10:00", "title": "公司发布年报", "content": "营收增长超预期"},
    ]
    telegraph_news = telegraph_news if telegraph_news is not None else [
        {"time": "2026-01-01 10:30", "title": "行业政策发布", "content": "政策利好行业"},
        {"time": "2026-01-01 10:40", "title": "资金流入", "content": "主力净流入增加"},
    ]
    with \
        patch("agents.news_agent.build_llm", return_value=fake_llm), \
        patch("agents.strategy_agent.build_llm", return_value=fake_llm), \
        patch("agents.risk_agent.build_llm", return_value=fake_llm), \
        patch("agents.telegraph_agent.build_llm", return_value=fake_llm), \
        patch("agents.news_agent.get_stock_news", return_value=news_items), \
        patch("agents.news_agent.get_stock_report", return_value=[]), \
        patch("agents.telegraph_agent.get_10jqka_news", return_value=telegraph_news), \
        patch("backtest.data.DataManager.get_data", return_value=_synthetic_df()), \
        patch("backtest.persistence.BacktestPersistence.save_result", return_value=""), \
        patch("agents.quant_agent._fetch_financials", return_value={"roe": 0.3}), \
        patch("agents.quant_agent._fetch_fund_flow", return_value={"主力净流入": 1000}), \
        patch("agents.quant_agent._fetch_industry_data", return_value={"行业": "白酒"}), \
        patch("agents.quant_agent._fetch_valuation_history", return_value={"latest_pe": 25.0}), \
        patch("agents.quant_agent._fetch_market_sentiment", return_value={"情绪描述": "中性"}):
        yield


def _make_llm(strategy=None, risk=None, news=_news_json_handler, telegraph=_telegraph_json_handler):
    strategy = strategy or StrategyCounter()
    risk = risk or RiskCounter(rejections=0)
    return FakeChatModel([
        ("首席风险官", risk),
        ("资讯侦察兵", news),
        ("市场动态分析师", telegraph),
        ("", strategy),
    ]), strategy, risk


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_e2e_full_pipeline_telegraph_wired_into_report():
    """B1 regression: telegraph analysis must flow into state AND the report."""
    fake, strategy, risk = _make_llm()
    with _patched_env(fake):
        final = create_alpha_flow_graph().invoke(_initial_state())

    assert not final.get("error"), final.get("error")
    # B1: telegraph data survives the graph and is JSON-shaped
    assert final["telegraph_analysis"]["analyzed_count"] == 2
    assert final["telegraph_analysis"]["market_sentiment"] == "乐观"
    assert len(final["telegraph_news"]) == 2
    # B1: strategy prompt received it (fake echoes a marker)
    assert "电报联动已验证" in final["strategy_report"]
    # B2 happy path: parse success flag survives
    assert final["news_parse_success"] is True
    # normal control flow
    assert final["risk_assessment"]["decision"] == "通过"
    assert final["count"] == 1
    assert strategy.calls == 1
    candidates = final["quant_data"]["backtest_candidates"]
    assert candidates and candidates[0]["metrics"]["sharpe"] >= 0
    # reasoning collected for the four LLM agents
    agents = {r["agent"] for r in final["reasoning_content"]}
    assert {"资讯侦察兵", "策略主理人", "风控官", "市场动态分析师"} <= agents


def test_e2e_revision_loop_regenerates_report():
    """Risk rejects once -> strategy regenerates with feedback -> passes."""
    strategy = StrategyCounter()
    risk = RiskCounter(rejections=1)
    fake = FakeChatModel([
        ("首席风险官", risk),
        ("资讯侦察兵", _news_json_handler),
        ("市场动态分析师", _telegraph_json_handler),
        ("", strategy),
    ])
    with _patched_env(fake):
        final = create_alpha_flow_graph().invoke(_initial_state())

    assert final["count"] == 2
    assert final["revision_needed"] is False
    assert final["risk_assessment"]["decision"] == "通过"
    assert strategy.calls == 2  # regenerated exactly once
    assert "第2次生成" in final["strategy_report"]
    assert "已回应修正请求" in final["strategy_report"]  # feedback reached strategy


def test_e2e_news_parse_failure_degrades_report():
    """B2 regression: parse failure must flip news_parse_success and degrade."""
    strategy = StrategyCounter()
    fake = FakeChatModel([
        ("首席风险官", RiskCounter(rejections=0)),
        ("资讯侦察兵", _news_garbage_handler),
        ("市场动态分析师", _telegraph_json_handler),
        ("", strategy),
    ])
    with _patched_env(fake):
        final = create_alpha_flow_graph().invoke(_initial_state())

    assert final["news_parse_success"] is False
    assert "资讯降级已验证" in final["strategy_report"]  # strategy saw the flag
    assert final["risk_assessment"]["decision"] == "通过"
    assert not final.get("error")


def test_e2e_telegraph_outage_does_not_block_pipeline():
    """Telegraph being unavailable must not fail or stall the analysis."""
    strategy = StrategyCounter()
    fake = FakeChatModel([
        ("首席风险官", RiskCounter(rejections=0)),
        ("资讯侦察兵", _news_json_handler),
        ("市场动态分析师", _telegraph_json_handler),
        ("", strategy),
    ])
    with _patched_env(fake, telegraph_news=[]):
        final = create_alpha_flow_graph().invoke(_initial_state())

    assert not final.get("error")
    assert final["telegraph_analysis"]["summary"] == "暂无同花顺新闻数据"
    assert final["strategy_report"].startswith("# 投资建议报告")
    assert final["risk_assessment"]["decision"] == "通过"


def test_e2e_telegraph_fetch_error_does_not_block_pipeline():
    """get_10jqka_news raising must degrade to a summary, not set state error."""

    def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    strategy = StrategyCounter()
    fake = FakeChatModel([
        ("首席风险官", RiskCounter(rejections=0)),
        ("资讯侦察兵", _news_json_handler),
        ("市场动态分析师", _telegraph_json_handler),
        ("", strategy),
    ])
    with patch("agents.news_agent.build_llm", return_value=fake), \
         patch("agents.strategy_agent.build_llm", return_value=fake), \
         patch("agents.risk_agent.build_llm", return_value=fake), \
         patch("agents.telegraph_agent.build_llm", return_value=fake), \
         patch("agents.news_agent.get_stock_news", return_value=[{"time": "t", "title": "x", "content": "y"}]), \
         patch("agents.news_agent.get_stock_report", return_value=[]), \
         patch("agents.telegraph_agent.get_10jqka_news", side_effect=_boom), \
         patch("backtest.data.DataManager.get_data", return_value=_synthetic_df()), \
         patch("backtest.persistence.BacktestPersistence.save_result", return_value=""), \
         patch("agents.quant_agent._fetch_financials", return_value={"roe": 0.3}), \
         patch("agents.quant_agent._fetch_fund_flow", return_value={}), \
         patch("agents.quant_agent._fetch_industry_data", return_value={}), \
         patch("agents.quant_agent._fetch_valuation_history", return_value={}), \
         patch("agents.quant_agent._fetch_market_sentiment", return_value={}):
        final = create_alpha_flow_graph().invoke(_initial_state())

    assert not final.get("error")
    assert "获取同花顺新闻失败" in final["telegraph_analysis"]["summary"]
    assert final["risk_assessment"]["decision"] == "通过"
