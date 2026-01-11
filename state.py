from typing import TypedDict, List, Dict, Any, Annotated
import operator

class AgentState(TypedDict):
    # 基本信息
    stock_code: str
    stock_name: str
    is_sector: bool # 是否为板块分析
    sector_type: str # "industry" or "concept"
    sector_cons: List[Dict[str, Any]] # 板块成分股
    
    # 数据层
    news_items: List[Dict[str, Any]] # 原始新闻列表
    news_analysis: str # LLM 对新闻的分析摘要
    sentiment_score: float # -1 to 1
    quant_data: Dict[str, Any]
    technical_indicators: Dict[str, Any]
    backtest_result: Dict[str, Any]
    
    # 决策层
    strategy_report: str
    risk_assessment: str
    
    # 控制流
    messages: Annotated[List[str], operator.add]
    next_node: str
    revision_needed: bool
    human_approval: bool # 人工审核状态
    count: int # 记录循环次数防止死循环
    is_web_mode: bool # 是否为网页模式
    reasoning_content: Annotated[List[Dict[str, str]], operator.add] # 存储各 Agent 的思考过程
    config: Dict[str, Any] # 存储每个用户独立的 API 和模型配置
    error: str # 存储节点错误信息，用于中止流程
