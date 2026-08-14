"""Unit tests for the news agent node.

news_agent_node is exercised with a mocked LLM and mocked data fetchers, so no
network / API key is required. Verifies output structure, score clamping and
the invalid-api-key path.
"""
from unittest.mock import patch, MagicMock

import pytest

from agents.news_agent import news_agent_node


class _FakeLLMResponse:
    def __init__(self, content, reasoning=""):
        self.content = content
        self.additional_kwargs = {"reasoning_content": reasoning}


def _base_state(**overrides):
    state = {
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
        },
        "error": "",
        "consecutive_failures": 0,
    }
    state.update(overrides)
    return state


@pytest.fixture
def mock_news_sources():
    with patch("agents.news_agent.get_stock_news", return_value=[
        {"新闻标题": "茅台业绩超预期", "发布时间": "2026-08-14", "新闻内容": "净利润增长20%"},
    ]), patch("agents.news_agent.get_stock_report", return_value=[
        {"预测": "目标价2000元"},
    ]), patch("agents.news_agent.get_board_news") as mock_board:
        yield mock_board


def test_invalid_api_key_returns_error_early(mock_news_sources):
    """Missing/invalid api_key short-circuits before any LLM call."""
    state = _base_state(config={"api_key": ""})
    result = news_agent_node(state)
    assert "Invalid API Key" in result["news_analysis"]
    assert result["sentiment_score"] == 0.0
    assert result["fear_greed_index"] == 50.0
    assert len(result["news_items"]) == 1  # news was still fetched


def test_parses_llm_json_and_clamps_scores(mock_news_sources):
    """A well-formed LLM JSON response drives the returned analysis."""
    llm_json = (
        '{"analysis": "业绩增长确定性高，白酒行业景气度延续，龙头地位稳固。", '
        '"sentiment_score": 1.8, "fear_greed_index": 120}'
    )
    with patch("agents.news_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _FakeLLMResponse(llm_json)
        mock_build.return_value = mock_llm

        result = news_agent_node(_base_state())

    assert mock_build.called
    assert "白酒" in result["news_analysis"]
    assert result["sentiment_score"] == 1.0  # clamped to [-1, 1]
    assert result["fear_greed_index"] == 100.0  # clamped to [0, 100]
    assert result["news_parse_success"] is True
    assert len(result["news_items"]) == 1
    assert result["reasoning_content"][0]["agent"] == "资讯侦察兵"


def test_short_analysis_marked_parse_failure(mock_news_sources):
    """Too-short analysis text is treated as a failed parse."""
    llm_json = '{"analysis": "好", "sentiment_score": 0.5, "fear_greed_index": 60}'
    with patch("agents.news_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _FakeLLMResponse(llm_json)
        mock_build.return_value = mock_llm

        result = news_agent_node(_base_state())

    assert result["news_parse_success"] is False
    assert result["sentiment_score"] == 0.0


def test_sector_mode_uses_board_news(mock_news_sources):
    """Sector analyses fetch board news instead of per-stock news."""
    mock_news_sources.return_value = [
        {"新闻标题": "白酒行业政策利好", "发布时间": "2026-08-14", "新闻内容": "行业复苏"},
    ]
    llm_json = (
        '{"analysis": "板块政策利好显著，行业估值有望迎来整体修复。", '
        '"sentiment_score": 0.6, "fear_greed_index": 70}'
    )
    with patch("agents.news_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _FakeLLMResponse(llm_json)
        mock_build.return_value = mock_llm

        result = news_agent_node(_base_state(
            is_sector=True,
            stock_code="BK0477",
            stock_name="白酒",
            sector_type="industry",
        ))

    mock_news_sources.assert_called_once_with("白酒", "industry")
    assert result["news_parse_success"] is True
