import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from graph import create_alpha_flow_graph
from tools.stock_data import search_stock_code, get_stock_hist_data, search_board_info, get_board_hist_data, get_board_cons, get_cache_status
import plotly.graph_objects as go
from pathlib import Path

# 页面配置
st.set_page_config(
    page_title="AlphaFlow 智能投资决策系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 加载环境变量，优先使用系统已设置的环境变量 (override=False)
load_dotenv(override=False)

# 模型探测缓存文件路径
MODEL_CACHE_FILE = Path(__file__).parent / ".model_cache.json"

def load_model_cache():
    """
    加载模型探测缓存
    如果缓存文件不存在或已过期，返回 None
    """
    try:
        if not MODEL_CACHE_FILE.exists():
            return None
        
        with open(MODEL_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 检查缓存是否过期（24小时）
        cache_time = datetime.fromisoformat(cache_data.get("cache_time", ""))
        if datetime.now() - cache_time > timedelta(hours=24):
            return None
        
        return cache_data.get("model_name")
    except Exception as e:
        return None

def save_model_cache(model_name: str):
    """
    保存模型探测结果到缓存文件
    """
    try:
        cache_data = {
            "model_name": model_name,
            "cache_time": datetime.now().isoformat()
        }
        with open(MODEL_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

# 初始化历史记录目录
HISTORY_DIR = "analysis_history"
if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)

def save_history(stock_name, stock_code, report):
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stock_code}.json"
    filepath = os.path.join(HISTORY_DIR, filename)
    data = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock_name": stock_name,
        "stock_code": stock_code,
        "report": report
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_history_list():
    if not os.path.exists(HISTORY_DIR):
        return []
    files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
    files.sort(reverse=True)
    return files

def delete_history(filename):
    filepath = os.path.join(HISTORY_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

def clear_all_history():
    if os.path.exists(HISTORY_DIR):
        for f in os.listdir(HISTORY_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(HISTORY_DIR, f))

# 初始化 Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "workflow_state" not in st.session_state:
    st.session_state.workflow_state = None
if "app" not in st.session_state:
    st.session_state.app = create_alpha_flow_graph()
if "current_stock" not in st.session_state:
    st.session_state.current_stock = None

# 侧边栏配置
with st.sidebar:
    st.title("⚙️ 系统配置")
    
    # 历史记录选项卡
    history_tab, config_tab = st.tabs(["🕒 历史记录", "🛠️ 配置"])
    
    with history_tab:
        history_files = get_history_list()
        if not history_files:
            st.info("暂无历史报告")
        else:
            if st.button("🗑️ 清空全部历史", width="stretch"):
                clear_all_history()
                st.rerun()
            st.divider()
            
            for h_file in history_files[:20]: # 显示最近20个
                try:
                    with open(os.path.join(HISTORY_DIR, h_file), "r", encoding="utf-8") as f:
                        h_data = json.load(f)
                        
                        col1, col2 = st.columns([0.8, 0.2])
                        with col1:
                            if st.button(f"{h_data['date']}\n{h_data['stock_name']}", key=f"btn_{h_file}", width="stretch"):
                                st.session_state.messages = [{"role": "assistant", "content": h_data['report']}]
                                st.rerun()
                        with col2:
                            # 使用 container 模式并设置按钮宽度，确保图标居中且不溢出
                            if st.button("❌", key=f"del_{h_file}", help="删除此记录", width="stretch"):
                                delete_history(h_file)
                                st.rerun()
                except:
                    pass

    with st.expander("📊 回测候选策略"):
        state = st.session_state.workflow_state or {}
        quant_data = state.get("quant_data", {})
        candidates = quant_data.get("backtest_candidates", [])
        if candidates:
            st.write(f"**找到 {len(candidates)} 个候选策略**")
            for i, cand in enumerate(candidates[:5]): # 显示前5个
                metrics = cand.get('metrics', {})
                with st.container():
                    col1, col2, col3 = st.columns(3)
                    col1.metric(f"{cand.get('name')}", f"{metrics.get('sharpe', 0):.2f}", "Sharpe")
                    col2.metric("CAGR", f"{metrics.get('cagr', 0)*100:.2f}%")
                    col3.metric("MDD", f"{metrics.get('max_drawdown', 0)*100:.2f}%")
                    if i < len(candidates[:5]) - 1:
                        st.divider()
        else:
            st.info("暂无可用的候选策略数据")

    with config_tab:
        # 获取默认模型，优先使用环境变量中的配置
        default_model = os.getenv("MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME") or "gpt-4o"
        common_models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "mimo-v2-flash"]
        
        # 如果是 DeepSeek 等自定义模型，添加到列表中
        if "deepseek" in default_model.lower() and "deepseek-v3" not in [m.lower() for m in common_models]:
             common_models.insert(0, default_model)
        elif default_model not in common_models:
            common_models.insert(0, default_model)
        
        selected_model = st.selectbox(
            "选择或输入分析模型",
            common_models,
            index=common_models.index(default_model) if default_model in common_models else 0
        )
        
        custom_model = st.text_input("自定义模型名称 (可选)", value=selected_model)
        model_to_use = custom_model if custom_model else selected_model
        
        st.divider()
        st.subheader("🔑 API 凭据配置")
        
        api_base = st.text_input(
            "API Base URL (代理地址)", 
            value=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        )
        api_key = st.text_input(
            "API Key", 
            value=os.getenv("OPENAI_API_KEY", ""), 
            type="password"
        )
        
        if not api_key:
            st.warning("⚠️ 请输入 API Key 以开始分析")
        
        temperature = st.slider("Temperature (随机性)", 0.0, 1.0, 0.3, 0.1)
        max_tokens = st.select_slider("Max Tokens (最大长度)", options=[1024, 2048, 4096, 8192, 8196, 16384, 32768], value=8196)
        
        thinking_mode = st.toggle("开启深度思考模式 (Thinking Mode)", value=True)
        
        if st.button("🗑️ 清除当前对话"):
            st.session_state.messages = []
            st.session_state.workflow_state = None
            st.rerun()

st.title("📈 AlphaFlow 智能投资决策系统")
st.caption("基于 LangGraph 的多智能体协作 A 股决策平台")

# 展示聊天历史
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 处理工作流逻辑
@st.cache_data(ttl=3600, show_spinner=False)
def _get_entity_info(input_str):
    """缓存版实体信息检索"""
    is_sector = False
    sector_type = ""
    sector_cons = []
    
    if input_str.isdigit() and len(input_str) == 6:
        return input_str, input_str, False, "", []
    
    board_info = search_board_info(input_str)
    if board_info:
        is_sector = True
        stock_code = board_info["code"]
        stock_name = board_info["name"]
        sector_type = board_info["type"]
        sector_cons = get_board_cons(stock_name, sector_type)
        return stock_code, stock_name, is_sector, sector_type, sector_cons
    
    stock_code, stock_name = search_stock_code(input_str)
    return stock_code, stock_name, False, "", []

def detect_available_model_st(api_key: str, api_base: str):
    """
    自动探测可用的模型 (Streamlit 版)
    返回第一个可用的模型名称，如果都不可用则返回 None
    """
    from langchain_openai import ChatOpenAI
    
    # 从环境变量获取支持的模型列表
    supported_models_str = os.getenv("SUPPORTED_MODELS", "")
    if supported_models_str:
        supported_models = [m.strip() for m in supported_models_str.split(",")]
    else:
        # 默认模型列表
        supported_models = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "mimo-v2-flash"]
    
    for model_name in supported_models:
        try:
            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=5,
                top_p=0.95,
                timeout=10
            )
            llm.invoke("hi")
            return model_name
        except Exception as e:
            continue
    
    return None

def validate_model_st(config_params):
    """模型可用性预检 (Streamlit 版) - 带持久化缓存和自动探测"""
    from langchain_openai import ChatOpenAI
    import hashlib
    
    # 1. 优先尝试用户当前选择的模型
    target_model = config_params.get("model_name")
    if target_model:
        try:
            llm = ChatOpenAI(
                model=target_model,
                api_key=config_params["api_key"],
                base_url=config_params["api_base"],
                max_tokens=5,
                top_p=0.95,
                timeout=10
            )
            llm.invoke("hi")
            return True, "", target_model
        except Exception as e:
            st.warning(f"⚠️ 选择的模型 {target_model} 验证失败，正在尝试缓存或自动探测...")

    # 2. 尝试从持久化缓存加载
    cached_model = load_model_cache()
    cache_key = hashlib.md5(
        f"{config_params['api_base']}_{config_params['model_name']}_{config_params['api_key']}".encode()
    ).hexdigest()
    
    # 检查 session 缓存
    if "model_validation_cache" not in st.session_state:
        st.session_state.model_validation_cache = {}
    
    if cache_key in st.session_state.model_validation_cache:
        cached_result = st.session_state.model_validation_cache[cache_key]
        # 检查缓存是否过期（5分钟）
        if (datetime.now() - cached_result["timestamp"]).total_seconds() < 300:
            return cached_result["is_ok"], cached_result["error"], cached_result["model"]
    
    # 执行验证
    try:
        llm = ChatOpenAI(
            model=config_params["model_name"], 
            api_key=config_params["api_key"], 
            base_url=config_params["api_base"], 
            max_tokens=5,
            top_p=0.95,
            timeout=10
        )
        llm.invoke("hi")
        result = (True, "", config_params["model_name"])
        
        # 保存到持久化缓存
        save_model_cache(config_params["model_name"])
    except Exception as e:
        # 如果指定的模型不可用，尝试自动探测
        st.info(f"🔍 模型 {config_params['model_name']} 不可用，正在自动探测可用模型...")
        available_model = detect_available_model_st(config_params["api_key"], config_params["api_base"])
        
        if available_model:
            st.success(f"✅ 自动探测到可用模型: {available_model}")
            result = (True, "", available_model)
            
            # 保存到持久化缓存
            save_model_cache(available_model)
        else:
            result = (False, str(e), None)
    
    # 保存到 session 缓存
    st.session_state.model_validation_cache[cache_key] = {
        "is_ok": result[0],
        "error": result[1],
        "model": result[2],
        "timestamp": datetime.now()
    }
    
    return result

def get_error_solutions(error_msg: str) -> list:
    """
    根据错误信息返回解决方案列表
    """
    solutions = []
    error_lower = error_msg.lower()
    
    if "400" in error_msg or "model" in error_lower or "not found" in error_lower:
        solutions.extend([
            "🔧 **模型不支持**: 请在侧边栏选择其他模型，或在 .env 文件中配置 SUPPORTED_MODELS",
            "🔧 **检查 API Base**: 确认 API Base URL 是否正确",
            "🔧 **检查 API Key**: 确认 API Key 是否有效且未过期"
        ])
    elif "401" in error_msg or "unauthorized" in error_lower or "invalid" in error_lower:
        solutions.extend([
            "🔧 **API Key 无效**: 请检查侧边栏的 API Key 是否正确",
            "🔧 **API Key 过期**: 请重新获取有效的 API Key",
            "🔧 **权限不足**: 确认 API Key 是否有访问该模型的权限"
        ])
    elif "timeout" in error_lower or "connection" in error_lower:
        solutions.extend([
            "🔧 **网络连接问题**: 请检查网络连接是否正常",
            "🔧 **API 服务不稳定**: 请稍后重试",
            "🔧 **代理问题**: 如果使用代理，请检查代理设置"
        ])
    elif "rate" in error_lower or "limit" in error_lower:
        solutions.extend([
            "🔧 **请求频率限制**: 请稍后重试",
            "🔧 **配额不足**: 请检查 API 配额是否充足"
        ])
    elif "akshare" in error_lower or "no tables found" in error_lower:
        solutions.extend([
            "🔧 **数据源问题**: AkShare 数据源可能暂时不可用",
            "🔧 **接口变更**: 数据接口可能已更新，请稍后重试",
            "🔧 **股票代码错误**: 请确认股票代码是否正确"
        ])
    else:
        solutions.extend([
            "🔧 **未知错误**: 请检查系统日志获取更多信息",
            "🔧 **联系支持**: 如果问题持续，请联系技术支持"
        ])
    
    return solutions

def run_workflow(input_str, config_params):
    # 0. 强校验 API Key
    if not config_params.get("api_key"):
        st.error("❌ 未配置 API Key，请在侧边栏配置后再试。")
        return
    
    # 模型可用性预检
    with st.status("🧪 正在验证模型可用性...", expanded=False) as status:
        is_ok, err, available_model = validate_model_st(config_params)
        if not is_ok:
            status.update(label="❌ 模型验证失败", state="error")
            st.error(f"模型验证失败: {err}")
            
            # 显示针对性的解决方案
            solutions = get_error_solutions(err)
            if solutions:
                st.info("💡 **可能的解决方案**:")
                for solution in solutions:
                    st.markdown(solution)
            return
        
        # 更新配置参数中的模型名称
        if available_model:
            config_params["model_name"] = available_model
            st.info(f"✅ 使用模型: {available_model}")
        
        status.update(label="✅ 模型验证通过", state="complete")

    # 1. 识别是股票还是板块
    with st.status("🔍 正在检索信息...", expanded=True) as status:
        stock_code, stock_name, is_sector, sector_type, sector_cons = _get_entity_info(input_str)
            
        if not stock_code:
            st.error(f"未找到匹配的股票或板块: {input_str}")
            return
            
        st.session_state.current_stock = {"code": stock_code, "name": stock_name, "is_sector": is_sector}
        type_str = "板块" if is_sector else "股票"
        status.update(label=f"✅ 已找到{type_str}: {stock_name} ({stock_code})", state="complete")

    # 2. 启动 LangGraph 工作流
    with st.status("🚀 AlphaFlow 多智能体协作中...", expanded=True) as status:
        st.write("📡 正在同步市场资讯与实时数据...")
        
        initial_state = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "is_sector": is_sector,
            "sector_type": sector_type,
            "sector_cons": sector_cons,
            "news_items": [],
            "news_analysis": "",
            "sentiment_score": 0.0,
            "quant_data": {
                "backtest_candidates": []
            },
            "technical_indicators": {},
            "strategy_report": "",
            "risk_assessment": "",
            "messages": [],
            "revision_needed": False,
            "human_approval": False,
            "count": 0,
            "error": "",
            "config": config_params
        }
        
        # 3. 运行图
        try:
            # 使用 stream 模式来捕获节点切换
            final_state = initial_state
            for output in st.session_state.app.stream(initial_state):
                for node_name, state_update in output.items():
                    final_state.update(state_update)
                    
                    if node_name == "supervisor":
                        st.write("🚀 **调度员**: 任务分发中...")
                    elif node_name == "news_node":
                        st.write("🕵️‍♂️ **资讯侦察兵**: 深度检索 AkShare 专业资讯完成")
                    elif node_name == "quant_node":
                        st.write("📊 **数据分析师**: 量化指标计算与多策略回测完成")
                    elif node_name == "strategy_node":
                        st.write("🧠 **策略主理人**: 正在综合研判并生成报告...")
                    elif node_name == "risk_node":
                        st.write("🛡️ **风控官**: 正在审核报告逻辑与合规性...")
            
            status.update(label="✅ 分析任务完成！", state="complete", expanded=False)
            st.session_state.workflow_state = final_state
            
            # 4. 展示结果
            display_results(final_state)
        except Exception as e:
            st.error(f"❌ 工作流运行失败: {str(e)}")
            
            # 显示针对性的解决方案
            solutions = get_error_solutions(str(e))
            if solutions:
                st.info("💡 **可能的解决方案**:")
                for solution in solutions:
                    st.markdown(solution)

def display_results(state):
    # 将报告加入消息历史
    report = state.get("strategy_report", "未生成报告")
    risk = state.get("risk_assessment", "未进行审核")
    reasonings = state.get("reasoning_content", [])
    stock_code = state.get("stock_code")
    stock_name = state.get("stock_name")
    is_sector = state.get("is_sector", False)
    
    # 0. 展示缓存状态
    cache_status = get_cache_status(stock_code)
    if cache_status and cache_status.get("data_sources"):
        with st.expander("📦 数据缓存状态"):
            st.info(f"缓存文件: {cache_status['cache_file']} | 总缓存条目: {cache_status['cache_size']}")
            
            data_sources = cache_status["data_sources"]
            if any(ds.get("last_updated") for ds in data_sources.values()):
                st.write("**各数据源最后更新时间:**")
                for source_name, source_info in data_sources.items():
                    last_updated = source_info.get("last_updated")
                    if last_updated:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(last_updated)
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                            st.write(f"- **{source_name}**: {time_str}")
                        except:
                            st.write(f"- **{source_name}**: {last_updated}")
                    else:
                        st.write(f"- **{source_name}**: 未缓存")
            else:
                st.write("暂无缓存数据")
    
    # 1. 展示价格走势图
    st.subheader(f"📈 {stock_name} ({stock_code}) {'板块' if is_sector else '股票'}价格走势")
    try:
        if is_sector:
            df = get_board_hist_data(stock_name, board_type=state.get("sector_type", "industry"), days=100)
        else:
            df = get_stock_hist_data(stock_code, days=100)
            
        if isinstance(df, pd.DataFrame) and not df.empty:
            fig = go.Figure(data=[go.Candlestick(x=df['日期'] if '日期' in df.columns else df.index,
                            open=df['开盘'],
                            high=df['最高'],
                            low=df['最低'],
                            close=df['收盘'],
                            name='K线')])
            fig.update_layout(xaxis_rangeslider_visible=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, width="stretch")
    except Exception as e:
        st.warning(f"无法加载 K 线图: {e}")

    # 2. 如果是板块，展示成分股
    if is_sector and state.get("sector_cons"):
        with st.expander("🔗 查看板块核心成分股"):
            cons_df = pd.DataFrame(state["sector_cons"])
            st.dataframe(cons_df, width="stretch")

    # 3. 展示思考过程 (如果有且开启了思考模式)
    if reasonings and state.get("config", {}).get("thinking_mode", True):
        with st.expander("🧠 查看 AI 深度思考过程"):
            for r in reasonings:
                st.write(f"**{r['agent']}**: ")
                st.info(r['content'])
    
    # 3. 展示分析结论与下载按钮
    
    # 处理结构化的风控结果
    if isinstance(risk, dict):
        decision = risk.get("decision", "未知")
        reason = risk.get("reason", "未提供详细理由")
        review_count = risk.get("review_count", 0)
        review_date = risk.get("review_date", "")
        
        risk_text = f"### �️ 风控意见\n\n【决策: {decision}】\n【审核次数: {review_count}】"
        if review_date:
            risk_text += f"\n【审核日期: {review_date}】"
        risk_text += f"\n\n{reason}"
        
        # 检查是否为强制通过
        if decision == "强制通过":
            risk_text += "\n\n---\n\n⚠️ **重要提示**: 该报告已达到最大修订次数，系统强制通过。\n\n⚠️ **风险提示**: 请仔细阅读风控官的末次风险提示，建议人工复核后再做投资决策。"
    else:
        # 兼容旧格式（字符串）
        risk_text = f"### 🛡️ 风控意见\n\n{risk}"
        
        # 检查是否为强制通过
        if "强制通过" in risk:
            risk_text += "\n\n---\n\n⚠️ **重要提示**: 该报告已达到最大修订次数，系统强制通过。\n\n⚠️ **风险提示**: 请仔细阅读风控官的末次风险提示，建议人工复核后再做投资决策。"
    
    full_content = f"### 📋 投资建议报告\n{report}\n\n---\n{risk_text}"
    
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.markdown(full_content)
    with col2:
        st.download_button(
            label="📥 下载报告",
            data=full_content,
            file_name=f"{stock_name}_{stock_code}_投资建议.md",
            mime="text/markdown"
        )
    
    # 4. 展示回测候选策略
    with st.expander("📈 回测候选策略详情"):
        quant_data = state.get("quant_data", {})
        candidates = quant_data.get("backtest_candidates", [])
        if candidates:
            st.write(f"**回测系统在 STRATEGY_REGISTRY 中发现了 {len(candidates)} 个候选策略**")
            for i, cand in enumerate(candidates):
                metrics = cand.get('metrics', {})
                with st.container():
                    st.write(f"### {i+1}. {cand.get('name')}")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Sharpe Ratio", f"{metrics.get('sharpe', 0):.2f}")
                    col2.metric("CAGR (年化收益)", f"{metrics.get('cagr', 0)*100:.2f}%")
                    col3.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0)*100:.2f}%")
                    col4.metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.2f}%")
                    
                    st.write("**策略摘要:**")
                    st.info(cand.get('summary', '暂无摘要'))
                    if i < len(candidates) - 1:
                        st.divider()
        else:
            st.info("暂无候选策略回测数据")

    with st.expander("📊 查看量化与财务数据底稿"):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.write("**技术面与形态识别**")
            tech = state.get("technical_indicators", {})
            patterns = tech.get("identified_patterns", [])
            if patterns:
                st.success(f"识别形态: {', '.join(patterns)}")
            st.json(tech)
        with col_d2:
            st.write("**财务、行业对比与资金面**")
            # 排除 backtest_candidates 以免冗余
            display_quant = {k: v for k, v in state.get("quant_data", {}).items() if k != "backtest_candidates"}
            st.json(display_quant)
            
    with st.expander("📰 查看最新资讯原文"):
        news = state.get("news_items", [])
        if isinstance(news, list) and news:
            for item in news:
                st.write(f"- **{item.get('新闻标题', '无标题')}** ({item.get('发布时间', '未知时间')})")
                st.caption(item.get('新闻内容', '无内容')[:200] + "...")
        else:
            st.write("暂无资讯数据")
    
    if state.get("news_analysis"):
        with st.expander("📝 资讯分析摘要"):
            st.write(state["news_analysis"])

    st.session_state.messages.append({"role": "assistant", "content": full_content})
    # 保存历史记录
    save_history(stock_name, stock_code, full_content)
    st.rerun()

# 聊天输入
if prompt := st.chat_input("请输入股票代码或名称 (如: 贵州茅台)", disabled=not api_key):
    # 开启新的搜索
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    # 构造配置参数
    config_params = {
        "model_name": model_to_use,
        "api_base": api_base,
        "api_key": api_key if api_key else os.getenv("OPENAI_API_KEY"),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking_mode": thinking_mode
    }
    run_workflow(prompt, config_params)

if not api_key:
    st.info("💡 请在侧边栏填写 API Key 后开始分析。")

