"""
工作流图定义模块

本模块定义了 AlphaFlow 系统的核心工作流图,使用 LangGraph 构建多智能体协作架构。

工作流架构:
    1. Supervisor (调度节点) - 入口节点,负责任务分发
    2. News Agent (资讯分析) - 并行节点,分析市场资讯和情绪
    3. Quant Agent (量化分析) - 并行节点,执行技术分析和回测
    4. Strategy Agent (策略生成) - 汇聚节点,综合生成投资建议
    5. Risk Agent (风险审核) - 审核节点,评估报告质量和风险

工作流特点:
    - 并行执行: News Agent 和 Quant Agent 同时运行,提高效率
    - 条件跳转: Risk Agent 审核不通过时返回 Strategy Agent 重新生成
    - 状态共享: 所有节点共享 AgentState,实现数据流转
"""

from langgraph.graph import StateGraph, END
from state import AgentState
from agents.news_agent import news_agent_node
from agents.quant_agent import quant_agent_node
from agents.strategy_agent import strategy_agent_node
from agents.risk_agent import risk_agent_node
from agents.telegraph_agent import telegraph_agent_node
from logger import get_logger

logger = get_logger(__name__)


def create_alpha_flow_graph():
    """
    创建 AlphaFlow 工作流图

    构建包含四个主要代理节点的工作流图:
    - news_node: 资讯分析代理
    - quant_node: 量化分析代理
    - strategy_node: 策略生成代理
    - risk_node: 风险审核代理

    工作流程:
        1. supervisor 节点作为入口,触发并行执行
        2. news_node 和 quant_node 并行处理资讯和量化数据
        3. 两个节点的结果汇聚到 strategy_node 生成策略报告
        4. strategy_node 的结果传递到 risk_node 进行审核
        5. risk_node 根据审核结果决定是否返回 strategy_node 重新生成或结束流程

    Returns:
        CompiledGraph: 编译后的 LangGraph 工作流对象,可直接用于执行

    Example:
        >>> graph = create_alpha_flow_graph()
        >>> result = graph.invoke(initial_state)
    """
    logger.info("正在创建 AlphaFlow 工作流图...")
    
    # 初始化状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("news_node", news_agent_node)
    workflow.add_node("quant_node", quant_agent_node)
    workflow.add_node("telegraph_node", telegraph_agent_node)
    workflow.add_node("strategy_node", strategy_agent_node)
    workflow.add_node("risk_node", risk_agent_node)
    
    # 调度节点（作为入口实现并行）
    def supervisor_node(state: AgentState):
        """
        调度节点函数

        作为工作流的入口节点,负责启动并行任务分发。

        Args:
            state: 当前工作流状态

        Returns:
            AgentState: 更新后的状态
        """
        logger.info("--- 🚀 调度员: 任务并行分发中 ---")
        return state

    workflow.add_node("supervisor", supervisor_node)
    workflow.set_entry_point("supervisor")
    
    # 构建边 - supervisor 并行分发到 news_node、quant_node 和 telegraph_node
    workflow.add_edge("supervisor", "news_node")
    workflow.add_edge("supervisor", "quant_node")
    workflow.add_edge("supervisor", "telegraph_node")
    
    # 并行节点汇聚到 strategy_node
    workflow.add_edge("news_node", "strategy_node")
    workflow.add_edge("quant_node", "strategy_node")
    workflow.add_edge("telegraph_node", "strategy_node")
    
    # strategy_node 的结果传递到 risk_node
    workflow.add_edge("strategy_node", "risk_node")
    
    # 风险审核后的条件跳转
    def after_risk_check(state: AgentState):
        """
        风险审核后的路由函数

        根据风险审核结果决定下一步操作:
        - 如果需要修订 (revision_needed=True),返回 strategy_node 重新生成
        - 如果审核通过,结束流程 (END)

        Args:
            state: 当前工作流状态

        Returns:
            str: 下一个节点的名称或 END 常量
        """
        if state.get("revision_needed"):
            logger.info("--- 🔄 风险审核未通过，返回策略层重新思考 ---")
            return "strategy_node"
        logger.info("--- ✅ 风险审核通过，流程结束 ---")
        return END
    
    workflow.add_conditional_edges(
        "risk_node",
        after_risk_check,
        {
            "strategy_node": "strategy_node",
            END: END
        }
    )
    
    logger.info("✅ AlphaFlow 工作流图创建完成")
    return workflow.compile()
