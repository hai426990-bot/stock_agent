"""Unit tests for the risk agent: fallback parsing + node behavior.

parse_risk_assessment_with_fallback is pure and tested directly; risk_agent_node
is exercised with a mocked LLM (no API calls).
"""
from unittest.mock import patch, MagicMock

import pytest

from agents.risk_agent import parse_risk_assessment_with_fallback, risk_agent_node


class TestParseRiskAssessmentWithFallback:
    def test_standard_json(self):
        result = parse_risk_assessment_with_fallback(
            '{"decision": "通过", "reason": "逻辑自洽"}'
        )
        assert result["decision"] == "通过"
        assert result["reason"] == "逻辑自洽"

    def test_empty_response_is_conservative(self):
        result = parse_risk_assessment_with_fallback("")
        assert result["decision"] == "驳回"

    def test_regex_extraction(self):
        result = parse_risk_assessment_with_fallback(
            '审核结论: decision: "驳回", reason: "数据与结论矛盾，存在重大硬伤"'
        )
        assert result["decision"] == "驳回"
        assert "矛盾" in result["reason"]

    def test_keyword_fallback(self):
        result = parse_risk_assessment_with_fallback("同意通过，无重大风险")
        assert result["decision"] == "通过"

    def test_garbage_defaults_to_reject(self):
        result = parse_risk_assessment_with_fallback("完全无关的文本内容")
        assert result["decision"] == "驳回"


class _FakeLLMResponse:
    def __init__(self, content, reasoning=""):
        self.content = content
        self.additional_kwargs = {"reasoning_content": reasoning}


def _base_state(**overrides):
    state = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "is_sector": False,
        "config": {
            "api_key": "test-key",
            "api_base": "https://api.example.com/v1",
            "model_name": "gpt-4o",
            "temperature": 0.5,
            "max_tokens": 4096,
            "thinking_mode": True,
        },
        "strategy_report": "看好该股票，技术面多头排列，风险提示充分。",
        "quant_data": {"backtest_candidates": []},
        "count": 0,
        "consecutive_failures": 0,
        "revision_needed": False,
        "error": "",
    }
    state.update(overrides)
    return state


def test_risk_node_approves_with_structured_result():
    with patch("agents.risk_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _FakeLLMResponse(
            '{"decision": "通过", "reason": "逻辑自洽，风险提示充分"}'
        )
        mock_build.return_value = mock_llm

        result = risk_agent_node(_base_state())

    assert result["risk_assessment"]["decision"] == "通过"
    assert result["revision_needed"] is False
    assert result["count"] == 1
    assert result["consecutive_failures"] == 0


def test_risk_node_rejects_and_requests_revision():
    with patch("agents.risk_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _FakeLLMResponse(
            '{"decision": "驳回", "reason": "数据全是利空但结论看多"}'
        )
        mock_build.return_value = mock_llm

        result = risk_agent_node(_base_state())

    assert result["risk_assessment"]["decision"] == "驳回"
    assert result["revision_needed"] is True
    assert result["count"] == 1


def test_risk_node_force_passes_at_max_revisions():
    """Beyond max_retries the decision becomes 强制通过."""
    with patch("agents.risk_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _FakeLLMResponse(
            '{"decision": "驳回", "reason": "仍有疑问"}'
        )
        mock_build.return_value = mock_llm

        result = risk_agent_node(_base_state(count=2))  # max_retries == 2

    assert result["risk_assessment"]["decision"] == "强制通过"
    assert result["revision_needed"] is False


def test_risk_node_llm_exception_recovers():
    """An LLM exception must not crash the node; it falls back to a rejection."""
    with patch("agents.risk_agent.build_llm") as mock_build:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("network down")
        mock_build.return_value = mock_llm

        result = risk_agent_node(_base_state())

    assert result["risk_assessment"]["decision"] == "驳回"
    assert "network down" in result["risk_assessment"]["reason"]
    assert result["count"] == 1


def test_risk_node_invalid_api_key():
    result = risk_agent_node(_base_state(config={"api_key": ""}))
    assert result["risk_assessment"] == "Error: Invalid API Key"
    assert result["revision_needed"] is False
