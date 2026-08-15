from typing import TypedDict, List, Dict, Any, Annotated
import operator

class AgentState(TypedDict, total=False):
    """工作流共享状态。

    注意：LangGraph 会**静默丢弃**节点返回的、未在此处声明的键
    （实测 langgraph 1.2.6），因此任何需要跨节点流转/持久化的字段
    必须在此声明，并配套端到端测试（tests/test_graph_e2e.py）防回归。
    """
    # 基本信息
    stock_code: str
    stock_name: str
    is_sector: bool  # 是否为板块分析
    sector_type: str  # "industry" or "concept"
    sector_cons: List[Dict[str, Any]]  # 板块成分股

    # 数据层
    news_items: List[Dict[str, Any]]  # 原始新闻列表
    news_analysis: str  # LLM 对新闻的分析摘要
    news_parse_success: bool  # 资讯 JSON 解析是否成功（strategy 据此降级）
    sentiment_score: float  # -1 to 1
    fear_greed_index: float  # 0 to 100
    telegraph_news: List[Dict[str, Any]]  # 同花顺实时新闻（含逐条 LLM 分析）
    telegraph_analysis: Dict[str, Any]  # 电报整体情绪/重要事件/机会汇总
    quant_data: Dict[str, Any]
    technical_indicators: Dict[str, Any]

    # 决策层
    strategy_report: str
    risk_assessment: Dict[str, Any]  # 结构化结果: decision/reason/review_count/review_date

    # 控制流
    messages: Annotated[List[str], operator.add]
    revision_needed: bool
    count: int  # 记录循环次数防止死循环
    reasoning_content: Annotated[List[Dict[str, str]], operator.add]  # 存储各 Agent 的思考过程
    config: Dict[str, Any]  # 存储每个用户独立的 API 和模型配置
    error: str  # 存储节点错误信息，用于中止流程
    consecutive_failures: Annotated[int, lambda x, y: y]  # 记录连续失败次数，用于熔断机制（总是取最新值）
