from langgraph.graph import StateGraph, END
from state import AgentState
from agents.news_agent import news_agent_node
from agents.quant_agent import quant_agent_node
from agents.strategy_agent import strategy_agent_node
from agents.risk_agent import risk_agent_node

def create_alpha_flow_graph():
    # 初始化状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("news_node", news_agent_node)
    workflow.add_node("quant_node", quant_agent_node)
    workflow.add_node("strategy_node", strategy_agent_node)
    workflow.add_node("risk_node", risk_agent_node)
    
    # 调度节点（作为入口实现并行）
    def supervisor_node(state: AgentState):
        print("--- 🚀 调度员: 任务并行分发中 ---")
        return state

    workflow.add_node("supervisor", supervisor_node)
    workflow.set_entry_point("supervisor")
    
    # 构建边
    workflow.add_edge("supervisor", "news_node")
    workflow.add_edge("supervisor", "quant_node")
    
    # 并行节点汇聚到 strategy_node
    workflow.add_edge("news_node", "strategy_node")
    workflow.add_edge("quant_node", "strategy_node")
    
    workflow.add_edge("strategy_node", "risk_node")
    
    # 风险审核后的跳转
    def after_risk_check(state: AgentState):
        if state.get("revision_needed"):
            print("--- 🔄 风险审核未通过，返回策略层重新思考 ---")
            return "strategy_node"
        return END
    
    workflow.add_conditional_edges(
        "risk_node",
        after_risk_check,
        {
            "strategy_node": "strategy_node",
            END: END
        }
    )
    
    return workflow.compile()
