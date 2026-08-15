"""state_builder: build the initial AgentState dict for create_alpha_flow_graph().

Ports app.py:529-537 (initial_state) and main.py:270-279 (config sub-dict).
"""
from typing import Any, Dict

from backend.analysis.models import AnalysisReport
from backend.configapp.services.config_bridge import build_agent_config


def build_initial_state(report: AnalysisReport) -> Dict[str, Any]:
    """Build the AgentState dict the graph expects, mirroring main.py.

    The `config` sub-dict carries the per-run LLM/backtest params the agents
    read (api_key, api_base, model_name, temperature, max_tokens, thinking_mode,
    backtest_lookback_days, backtest_initial_cash).

    NOTE: keys must stay in sync with state.AgentState — LangGraph silently
    drops node-returned keys that are not declared in the state schema.
    """
    config = build_agent_config()
    # Web 模式标记：quant_agent 据此把回测结果入库 BacktestResult 并关联本报告
    config["report_id"] = str(report.id)
    return {
        "stock_code": report.stock_code,
        "stock_name": report.stock_name,
        "is_sector": report.is_sector,
        "sector_type": report.sector_type or "",
        "sector_cons": list(report.sector_cons or []),
        # data layer
        "news_items": [],
        "news_analysis": "",
        "news_parse_success": True,
        "sentiment_score": 0.0,
        "fear_greed_index": 0.0,
        "telegraph_news": [],
        "telegraph_analysis": {},
        "quant_data": {"backtest_candidates": []},
        "technical_indicators": {},
        # decision layer
        "strategy_report": "",
        "risk_assessment": {},
        # control flow
        "messages": [],
        "revision_needed": False,
        "count": 0,
        "human_approved": False,
        "approval_rejections": 0,
        "approval_comment": "",
        "reasoning_content": [],
        "config": config,
        "error": "",
        "consecutive_failures": 0,
    }


def project_serializable(state: Dict[str, Any]) -> Dict[str, Any]:
    """Project the final AgentState onto a JSON-serializable dict for storage.

    Drops control-flow / transient fields the frontend doesn't need and that
    may not be JSON-safe (e.g. raw config with api_key). Keeps the decision +
    data layers the report tabs render.
    """
    keep = (
        "stock_code", "stock_name", "is_sector", "sector_type", "sector_cons",
        "news_items", "news_analysis", "news_parse_success", "sentiment_score",
        "fear_greed_index", "telegraph_news", "telegraph_analysis",
        "quant_data", "technical_indicators",
        "strategy_report", "risk_assessment",
    )
    out = {}
    for k in keep:
        if k in state:
            out[k] = state[k]
    return out
