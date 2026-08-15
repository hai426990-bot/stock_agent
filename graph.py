"""
工作流图定义模块

本模块定义了 AlphaFlow 系统的核心工作流图,使用 LangGraph 构建多智能体协作架构。

工作流架构:
    1. Supervisor (调度节点) - 入口节点,负责任务分发
    2. News Agent (资讯分析) - 并行节点,分析市场资讯和情绪
    3. Quant Agent (量化分析) - 并行节点,执行技术分析和回测
    4. Strategy Agent (策略生成) - 汇聚节点,综合生成投资建议
    5. Risk Agent (风险审核) - 审核节点,评估报告质量和风险
    6. Approval Gate (人工审批) - 可选门节点,启用时用 interrupt() 挂起等待用户批准

工作流特点:
    - 并行执行: News Agent 和 Quant Agent 同时运行,提高效率
    - 条件跳转: Risk Agent 审核不通过时返回 Strategy Agent 重新生成;
      审核通过后进入人工审批门(仅当 human_approval.enabled=True),驳回则带着
      审批意见回到 Strategy Agent 修订,超过驳回上限自动放行
    - 状态共享: 所有节点共享 AgentState,实现数据流转
    - 人工审批: 图以 MemorySaver checkpointer 编译,approval 节点通过
      langgraph.types.interrupt() 挂起,由 orchestrator 收到 __interrupt__ 事件后
      等待用户 POST 审批,再以 Command(resume=...) 恢复同一线程
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from state import AgentState
from agents.news_agent import news_agent_node
from agents.quant_agent import quant_agent_node
from agents.strategy_agent import strategy_agent_node
from agents.risk_agent import risk_agent_node
from agents.telegraph_agent import telegraph_agent_node
from logger import get_logger

logger = get_logger(__name__)


def approval_gate_node(state: AgentState):
    """人工审批门节点。

    未启用审批 (human_approval_enabled=False) 时直接放行,行为与旧版一致。
    启用时:第一次进入以 interrupt() 挂起,把风控结论作为 payload 交给编排层
    推送 SSE 事件;用户通过 POST /api/analysis/{id}/approval 提交
    {"approved": bool, "comment": str} 后,同一节点恢复执行:
      - 通过 -> human_approved=True, 流向 END
      - 驳回 -> 带审批意见回到 strategy_node 修订;驳回次数达到上限后自动放行,
        避免人机循环死锁。

    注意: interrupt() 要求图以 checkpointer 编译且以 thread_id 调用(编排层负责)。
    """
    config = state.get("config", {})
    if not config.get("human_approval_enabled"):
        return {"human_approved": True}

    if state.get("human_approved"):
        return {"human_approved": True}

    assessment = state.get("risk_assessment", {}) or {}
    verdict = interrupt({
        "decision": assessment.get("decision", "通过"),
        "reason": assessment.get("reason", ""),
        "review_count": assessment.get("review_count", 0),
        "rejections": state.get("approval_rejections", 0),
    })
    approved = bool(verdict and verdict.get("approved"))

    if approved:
        return {"human_approved": True}

    rejections = state.get("approval_rejections", 0) + 1
    max_rejections = int(config.get("human_approval_max_rejections", 3))
    comment = (verdict or {}).get("comment", "") or "报告未通过人工审批,请修订"
    if rejections > max_rejections:
        logger.warning(f"人工驳回已达上限 ({max_rejections})，自动放行")
        return {"human_approved": True, "approval_rejections": rejections}
    logger.info(f"--- 🧑‍💼 人工审批驳回 (第 {rejections} 次): {comment} ---")
    return {
        "human_approved": False,
        "approval_rejections": rejections,
        "approval_comment": comment,
        "revision_needed": True,  # 返回策略层修订
    }


def create_alpha_flow_graph():
    """
    创建 AlphaFlow 工作流图

    构建包含四个主要代理节点的工作流图:
    - news_node: 资讯分析代理
    - quant_node: 量化分析代理
    - telegraph_node: 电报分析代理 (并行, 失败不阻塞)
    - strategy_node: 策略生成代理
    - risk_node: 风险审核代理
    - approval_gate: 人工审批门 (可选, 默认关闭)

    工作流程:
        1. supervisor 节点作为入口,触发并行执行
        2. news_node / quant_node / telegraph_node 并行处理
        3. 三个节点的结果汇聚到 strategy_node 生成策略报告
        4. strategy_node 的结果传递到 risk_node 进行审核
        5. risk_node 根据审核结果决定返回 strategy_node 重新生成,
           或进入 approval_gate 人工审批门(若启用)
        6. 审批通过(或未启用) -> END; 驳回 -> 返回 strategy_node 修订

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
    workflow.add_node("approval_gate", approval_gate_node)
    
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
        - 如果审核通过,进入人工审批门 (approval_gate)

        Args:
            state: 当前工作流状态

        Returns:
            str: 下一个节点的名称
        """
        if state.get("revision_needed"):
            logger.info("--- 🔄 风险审核未通过，返回策略层重新思考 ---")
            return "strategy_node"
        logger.info("--- ✅ 风险审核通过，进入人工审批门 ---")
        return "approval_gate"
    
    workflow.add_conditional_edges(
        "risk_node",
        after_risk_check,
        {
            "strategy_node": "strategy_node",
            "approval_gate": "approval_gate",
        }
    )

    # 人工审批后的条件跳转
    def after_approval(state: AgentState):
        if state.get("human_approved"):
            logger.info("--- ✅ 人工审批通过，流程结束 ---")
            return END
        logger.info("--- 🔄 人工审批驳回，返回策略层修订 ---")
        return "strategy_node"

    workflow.add_conditional_edges(
        "approval_gate",
        after_approval,
        {
            "strategy_node": "strategy_node",
            END: END,
        }
    )
    
    logger.info("✅ AlphaFlow 工作流图创建完成")
    # 以 MemorySaver 编译以支持 interrupt() 人工审批。
    # 注意: checkpoints 按 thread_id 在内存中累积(单进程部署场景可接受;
    # 如需清理或跨进程恢复, 可替换为 langgraph-checkpoint-sqlite 的 SqliteSaver)。
    return workflow.compile(checkpointer=MemorySaver())
