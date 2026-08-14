"""config_bridge: thin wrapper around the existing ConfigManager.

Single-user personal tool, so config lives in config_default.json + config_user.json
+ env (the 4-tier merge ConfigManager already does). No DB model needed.

This module is the ONLY place the backend touches ConfigManager, so the rest of
the backend is decoupled from the file-based config mechanism.
"""
from typing import Any, Dict

from config import get_config_manager

# Keys the agents actually read from AgentState["config"].
# Must stay in sync with agents/{news,quant,risk,strategy,telegraph}_agent.py
# (they read via config.get(key, default)).
AGENT_CONFIG_KEYS = (
    "api_key",
    "api_base",
    "model_name",
    "temperature",
    "max_tokens",
    "thinking_mode",
    "backtest_lookback_days",
    "backtest_initial_cash",
    # quant_agent backtest extras
    "backtest_sector_days",
    "backtest_commission",
    "backtest_slippage",
    "backtest_max_runs",
    # news_agent multi-source extras
    "news_rss_urls",
    "news_enable_reddit",
    "news_enable_x",
    "news_rss_limit",
    "news_reddit_limit",
    "news_x_limit",
)


def _cm():
    """Return the global ConfigManager (rooted at the AlphaFlow project root)."""
    return get_config_manager()


def get_effective_config() -> Dict[str, Any]:
    """Full merged config (default > env > user > runtime).

    The api_key value is preserved here (this dict is for internal use, e.g. the
    orchestrator). Use mask_config() for any API response.
    """
    return _cm().get_all()


def mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of config safe for API responses: the raw api_key is
    replaced with a boolean has_api_key flag."""
    out = {k: v for k, v in config.items()}
    if "api_key" in out:
        out["has_api_key"] = bool(out.get("api_key"))
        out["api_key"] = ""
    return out


def build_agent_config() -> Dict[str, Any]:
    """Build the flat config dict the agents expect in AgentState["config"].

    Reads from the merged ConfigManager so the 4-tier priority
    (default > env > user > runtime) is respected. Defaults mirror the
    fallbacks hardcoded in the agents so web mode behaves identically to CLI.
    """
    cm = _cm()
    return {
        "api_key": cm.get("api_key", ""),
        "api_base": cm.get("api_base", "https://api.openai.com/v1"),
        "model_name": cm.get("model_name", "gpt-4o"),
        "temperature": cm.get("llm.temperature", 0.5),
        "max_tokens": cm.get("llm.max_tokens", 4096),
        "thinking_mode": cm.get("llm.thinking_mode", True),
        "backtest_lookback_days": cm.get("backtest.days", 365),
        "backtest_initial_cash": cm.get("backtest.cash", 100000.0),
        "backtest_sector_days": cm.get("backtest.sector_days", 252),
        "backtest_commission": cm.get("backtest.commission", 0.0003),
        "backtest_slippage": cm.get("backtest.slippage", 0.001),
        "backtest_max_runs": cm.get("backtest.max_runs", 20),
        "news_rss_urls": cm.get("news.rss_urls", ""),
        "news_enable_reddit": cm.get("news.enable_reddit", False),
        "news_enable_x": cm.get("news.enable_x", False),
        "news_rss_limit": cm.get("news.rss_limit", 12),
        "news_reddit_limit": cm.get("news.reddit_limit", 12),
        "news_x_limit": cm.get("news.x_limit", 12),
    }


def save_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist non-secret config to config_user.json via ConfigManager.

    Accepts the same shape as get_effective_config() returns. The api_key, if
    provided, is also persisted (config_user.json is gitignored). Returns the
    masked effective config after saving.
    """
    cm = _cm()
    user_config = cm.get_user_config()

    # Top-level scalar keys
    for key in ("api_key", "api_base", "model_name"):
        if key in payload and payload[key] is not None:
            user_config[key] = payload[key]

    # supported_models (list)
    if "supported_models" in payload and payload["supported_models"] is not None:
        user_config["supported_models"] = payload["supported_models"]

    # Nested llm.* keys
    llm_in = payload.get("llm") or {}
    if llm_in:
        user_config.setdefault("llm", {})
        for key in ("temperature", "max_tokens", "thinking_mode"):
            if key in llm_in and llm_in[key] is not None:
                user_config["llm"][key] = llm_in[key]

    # Nested backtest.* keys
    bt_in = payload.get("backtest") or {}
    if bt_in:
        user_config.setdefault("backtest", {})
        for key in ("days", "cash", "commission", "slippage", "max_runs", "sector_days"):
            if key in bt_in and bt_in[key] is not None:
                user_config["backtest"][key] = bt_in[key]

    cm.save_user_config(user_config)
    cm.reload()
    return mask_config(get_effective_config())


def get_supported_models():
    """List of model names for the frontend dropdown."""
    return _cm().get("supported_models", ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "mimo-v2-flash"])
