"""共享的 LLM 构造工具。

4 个 Agent 之前各自复制了一份相同的配置提取 + ChatOpenAI 初始化样板
（模型名/温度/token 截断/深度思考开关）。这里收敛为单一实现，
所有 Agent 通过 build_llm(config) 获取 LLM 实例。
"""
from typing import Any, Dict

from langchain_openai import ChatOpenAI

# 不支持深度思考(extra_body thinking)的模型名关键词
NO_THINKING_KEYWORDS = ("mimo", "flash")

# 各 Agent 的默认模型/温度兜底（与历史行为保持一致）
DEFAULT_MODEL = "gpt-3.5-turbo"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 4096


def build_llm(config: Dict[str, Any], max_tokens_cap: int = 4096) -> ChatOpenAI:
    """根据 AgentState["config"] 构造 ChatOpenAI 实例。

    统一处理:
      - 模型名 / 温度 / max_tokens 截断（防止空响应）
      - 深度思考模式（仅对支持的模型启用，排除 mimo/flash 系）

    Args:
        config: AgentState["config"] 字典（由 state_builder / main.py 构造）
        max_tokens_cap: 该 Agent 允许的最大 token 数（strategy 用 16384）

    Returns:
        配置好的 ChatOpenAI 实例
    """
    model_name = config.get("model_name", DEFAULT_MODEL)
    temperature = config.get("temperature", DEFAULT_TEMPERATURE)
    max_tokens = config.get("max_tokens", DEFAULT_MAX_TOKENS)
    api_base = config.get("api_base", "https://api.openai.com/v1")
    api_key = config.get("api_key")

    llm_kwargs = {
        "model": model_name,
        "temperature": temperature,
        "max_tokens": min(int(max_tokens), max_tokens_cap),
        "top_p": 0.95,
        "base_url": api_base,
        "api_key": api_key,
    }

    # 只对支持深度思考的模型启用（排除 mimo-v2-flash 等）
    if config.get("thinking_mode") and not any(
        x in model_name.lower() for x in NO_THINKING_KEYWORDS
    ):
        llm_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        print(f"✅ 已启用深度思考模式")
    else:
        print(f"ℹ️ 已禁用深度思考模式（模型: {model_name}）")

    return ChatOpenAI(**llm_kwargs)
