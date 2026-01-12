import streamlit as st
import pandas as pd
import os
import json
import hashlib
import shutil
from datetime import datetime, timedelta
from dotenv import load_dotenv
from graph import create_alpha_flow_graph
from tools.stock_data import search_stock_code, get_stock_hist_data, search_board_info, get_board_hist_data, get_board_cons, get_cache_status, clear_akshare_cache
import plotly.graph_objects as go
from pathlib import Path

# 页面配置
st.set_page_config(
    page_title="AlphaFlow 智能投资决策系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 加载环境变量，优先使用 .env 配置文件 (override=True)
load_dotenv(override=True)

# 模型探测缓存文件路径
MODEL_CACHE_FILE = Path(__file__).parent / ".model_cache.json"

def inject_global_css():
    st.markdown(
        """
        <style>
        /* Typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="css"]  {
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
        }

        /* App background */
        [data-testid="stAppViewContainer"]{
          background: radial-gradient(900px 420px at 10% 0%, rgba(99,102,241,0.12), transparent 50%),
                      radial-gradient(900px 420px at 90% 0%, rgba(16,185,129,0.10), transparent 55%),
                      linear-gradient(180deg, #f8fafc 0%, #ffffff 45%, #ffffff 100%);
        }

        /* Markdown styling */
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3{
          letter-spacing: -0.02em;
          color: #0f172a;
        }
        .stMarkdown h1{ font-weight: 800; }
        .stMarkdown h2{ font-weight: 750; border-left: 4px solid #6366f1; padding-left: 10px; }
        .stMarkdown h3{ font-weight: 700; }
        .stMarkdown p, .stMarkdown li{
          color: #0f172a;
          line-height: 1.6;
        }
        .stMarkdown strong{
          color: #111827;
          background: linear-gradient(180deg, rgba(99,102,241,0.16), rgba(99,102,241,0.0));
          padding: 0 2px;
          border-radius: 4px;
        }
        .stMarkdown blockquote{
          border-left: 4px solid #94a3b8;
          padding: 10px 14px;
          margin: 10px 0;
          background: rgba(148,163,184,0.10);
          border-radius: 10px;
          color: #0f172a;
        }
        .stMarkdown code{
          background: rgba(2,6,23,0.06);
          padding: 2px 6px;
          border-radius: 8px;
        }
        .stMarkdown table{
          border-collapse: separate;
          border-spacing: 0;
          overflow: hidden;
          border-radius: 14px;
          border: 1px solid rgba(148,163,184,0.25);
        }
        .stMarkdown thead tr{
          background: rgba(99,102,241,0.10);
        }
        .stMarkdown tbody tr:nth-child(even){
          background: rgba(2,6,23,0.03);
        }

        /* Cards */
        .af-card{
          border: 1px solid rgba(148,163,184,0.25);
          background: rgba(255,255,255,0.75);
          backdrop-filter: blur(6px);
          border-radius: 16px;
          padding: 14px 14px;
        }
        .af-hero{
          border: 1px solid rgba(148,163,184,0.25);
          background: linear-gradient(135deg, rgba(99,102,241,0.18), rgba(16,185,129,0.10));
          border-radius: 18px;
          padding: 18px 18px;
        }
        .af-muted{ color: #475569; }
        .af-title{ font-size: 26px; font-weight: 800; color:#0f172a; letter-spacing:-0.03em; margin:0; }
        .af-subtitle{ margin: 4px 0 0 0; color:#334155; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _badge(text: str, fg: str = "#0f172a", bg: str = "#e2e8f0") -> str:
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{bg};color:{fg};font-size:12px;line-height:18px;margin-right:6px'>{text}</span>"

def _keyify(*parts: object) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

def _strategy_icon(sharpe: float) -> str:
    if sharpe >= 1.5:
        return "🚀"
    if sharpe >= 1.0:
        return "⭐"
    if sharpe >= 0.5:
        return "✅"
    if sharpe >= 0.0:
        return "⚖️"
    return "🧊"

def _sharpe_badge(sharpe: float) -> str:
    if sharpe >= 1.5:
        return _badge(f"Sharpe {sharpe:.2f}", fg="#14532d", bg="#dcfce7")
    if sharpe >= 1.0:
        return _badge(f"Sharpe {sharpe:.2f}", fg="#0f766e", bg="#ccfbf1")
    if sharpe >= 0.5:
        return _badge(f"Sharpe {sharpe:.2f}", fg="#1d4ed8", bg="#dbeafe")
    if sharpe >= 0.0:
        return _badge(f"Sharpe {sharpe:.2f}", fg="#a16207", bg="#fef9c3")
    return _badge(f"Sharpe {sharpe:.2f}", fg="#991b1b", bg="#fee2e2")

def _mdd_badge(mdd: float) -> str:
    # mdd is negative
    if mdd >= -0.12:
        return _badge(f"MDD {mdd*100:.1f}%", fg="#14532d", bg="#dcfce7")
    if mdd >= -0.25:
        return _badge(f"MDD {mdd*100:.1f}%", fg="#a16207", bg="#fef9c3")
    return _badge(f"MDD {mdd*100:.1f}%", fg="#991b1b", bg="#fee2e2")

def _fingerprint_secret(secret: str) -> str:
    if not secret:
        return "none"
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8]

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
                except Exception:
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
                    sharpe = float(metrics.get("sharpe", 0) or 0)
                    mdd = float(metrics.get("max_drawdown", 0) or 0)
                    title = cand.get("label") or cand.get("name")
                    st.markdown(f"{_strategy_icon(sharpe)} <b>{i+1}. {title}</b><br>{_sharpe_badge(sharpe)}{_mdd_badge(mdd)}", unsafe_allow_html=True)

                    col1, col2, col3 = st.columns(3)
                    col1.metric("CAGR", f"{metrics.get('cagr', 0)*100:.2f}%")
                    col2.metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.2f}%")
                    col3.metric("MDD", f"{metrics.get('max_drawdown', 0)*100:.2f}%")
                    if i < len(candidates[:5]) - 1:
                        st.divider()
        else:
            st.info("暂无可用的候选策略数据")

    with st.expander("🗄️ 缓存状态"):
        current = st.session_state.get("current_stock") or {}
        stock_code = current.get("code")
        st.json(get_cache_status(stock_code))

    with config_tab:
        # 获取默认模型，优先使用环境变量中的配置
        default_model = os.getenv("MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME") or os.getenv("OPENAI_MODEL") or "gpt-4o"
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
            value=os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
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

        st.divider()
        st.subheader("📊 回测参数")
        backtest_lookback_days = st.number_input("回测回溯天数", min_value=30, max_value=3650, value=365, step=30)
        backtest_sector_days = st.number_input("板块回测天数", min_value=30, max_value=3650, value=252, step=30)
        backtest_initial_cash = st.number_input("初始资金", min_value=1000.0, max_value=1e9, value=100000.0, step=10000.0)
        backtest_commission = st.number_input("手续费率(单边)", min_value=0.0, max_value=0.02, value=0.0003, step=0.0001, format="%.4f")
        backtest_slippage = st.number_input("滑点(单边)", min_value=0.0, max_value=0.05, value=0.001, step=0.0005, format="%.4f")

        st.divider()
        st.subheader("🧹 本地缓存")
        if st.button("清理本地缓存（不影响历史报告）", help="会清理 AkShare/模型探测/回测缓存，并刷新 Streamlit cache"):
            try:
                clear_akshare_cache(ttl_seconds=0)
            except Exception:
                pass

            for file_path in [Path(".akshare_cache.json"), MODEL_CACHE_FILE]:
                try:
                    if file_path.exists():
                        file_path.unlink()
                except Exception:
                    pass

            for dir_path in [Path(".backtest_cache"), Path(".backtest_results")]:
                try:
                    if dir_path.exists():
                        shutil.rmtree(dir_path, ignore_errors=True)
                except Exception:
                    pass

            try:
                st.cache_data.clear()
            except Exception:
                pass

            st.success("已清理本地缓存")
        
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
    supported_models_str = os.getenv("SUPPORTED_MODELS") or os.getenv("OPENAI_MODEL") or ""
    if supported_models_str:
        if "," in supported_models_str:
            supported_models = [m.strip() for m in supported_models_str.split(",")]
        else:
            supported_models = [supported_models_str.strip()]
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
            llm_kwargs = {
                "model": target_model,
                "api_key": config_params["api_key"],
                "base_url": config_params["api_base"],
                "max_tokens": 5,
                "top_p": 0.95,
                "timeout": 10
            }
            if config_params.get("thinking_mode"):
                llm_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
                
            llm = ChatOpenAI(**llm_kwargs)
            llm.invoke("hi")
            return True, "", target_model
        except Exception as e:
            st.warning(f"⚠️ 选择的模型 {target_model} 验证失败，正在尝试缓存或自动探测...")

    # 2. 尝试从持久化缓存加载
    cached_model = load_model_cache()
    cache_key = hashlib.md5(
        f"{config_params['api_base']}_{config_params['model_name']}_{_fingerprint_secret(config_params.get('api_key'))}_{config_params.get('thinking_mode')}".encode()
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
        llm_kwargs = {
            "model": config_params["model_name"], 
            "api_key": config_params["api_key"], 
            "base_url": config_params["api_base"], 
            "max_tokens": 5,
            "top_p": 0.95,
            "timeout": 10
        }
        if config_params.get("thinking_mode"):
            llm_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            
        llm = ChatOpenAI(**llm_kwargs)
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
    inject_global_css()
    # 将报告加入消息历史
    report = state.get("strategy_report", "未生成报告")
    risk = state.get("risk_assessment", "未进行审核")
    reasonings = state.get("reasoning_content", [])
    stock_code = state.get("stock_code")
    stock_name = state.get("stock_name")
    is_sector = state.get("is_sector", False)
    sentiment = float(state.get("sentiment_score", 0.0) or 0.0)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Hero header
    type_str = "板块" if is_sector else "股票"
    st.markdown(
        f"""
        <div class="af-hero">
          <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-end">
            <div>
              <div class="af-title">AlphaFlow 报告 · {stock_name} ({stock_code})</div>
              <div class="af-subtitle">{type_str} · 生成时间 {now_str}</div>
            </div>
            <div style="text-align:right">
              {_badge('资讯情绪', fg='#0f172a', bg='#e2e8f0')}
              {_badge(f'{sentiment:+.2f}', fg=('#14532d' if sentiment>0.15 else '#991b1b' if sentiment<-0.15 else '#0f172a'),
                     bg=('#dcfce7' if sentiment>0.15 else '#fee2e2' if sentiment<-0.15 else '#e2e8f0'))}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
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
            st.plotly_chart(fig, width="stretch", key=f"kline_{stock_code}")
    except Exception as e:
        st.warning(f"无法加载 K 线图: {e}")

    # 2. 如果是板块，展示成分股
    if is_sector and state.get("sector_cons"):
        with st.expander("🔗 查看板块核心成分股"):
            cons_df = pd.DataFrame(state["sector_cons"])
            st.dataframe(cons_df, width="stretch")

    # 3. 展示思考过程移至 Tabs
    
    # 3. 展示分析结论与下载按钮
    
    # 处理结构化的风控结果
    if isinstance(risk, dict):
        decision = risk.get("decision", "未知")
        reason = risk.get("reason", "未提供详细理由")
        review_count = risk.get("review_count", 0)
        review_date = risk.get("review_date", "")
        
        risk_text = f"### 🛡️ 风控意见\n\n【决策: {decision}】\n【审核次数: {review_count}】"
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
    
    # KPI row (derived from best backtest candidate)
    quant_data = state.get("quant_data", {})
    candidates = quant_data.get("backtest_candidates", []) or []
    top = candidates[0] if candidates else {}
    top_metrics = (top.get("metrics") or {}) if isinstance(top, dict) else {}
    top_sharpe = float(top_metrics.get("sharpe", 0) or 0)
    top_cagr = float(top_metrics.get("cagr", 0) or 0)
    top_mdd = float(top_metrics.get("max_drawdown", 0) or 0)
    top_turnover = float(top_metrics.get("turnover", 0) or 0)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"<div class='af-card'><div class='af-muted'>⭐ 最佳 Sharpe</div><div style='font-size:22px;font-weight:800'>{top_sharpe:.2f}</div></div>", unsafe_allow_html=True)
    with k2:
        st.markdown(f"<div class='af-card'><div class='af-muted'>📈 最佳 CAGR</div><div style='font-size:22px;font-weight:800'>{top_cagr*100:.2f}%</div></div>", unsafe_allow_html=True)
    with k3:
        st.markdown(f"<div class='af-card'><div class='af-muted'>🧯 最佳 MDD</div><div style='font-size:22px;font-weight:800'>{top_mdd*100:.2f}%</div></div>", unsafe_allow_html=True)
    with k4:
        st.markdown(f"<div class='af-card'><div class='af-muted'>🔁 换手 (Turnover)</div><div style='font-size:22px;font-weight:800'>{top_turnover:.3f}</div></div>", unsafe_allow_html=True)

    tabs = st.tabs(["🧾 报告正文", "🛡️ 风控结论", "📈 回测策略", "🧠 思考过程"])

    with tabs[0]:
        st.markdown("<div class='af-card'>", unsafe_allow_html=True)
        st.markdown("## 🧾 投资建议报告（结构化正文）")
        st.markdown(report)
        st.markdown("</div>", unsafe_allow_html=True)
        st.download_button(
            label="📥 下载报告（Markdown）",
            data=full_content,
            file_name=f"{stock_name}_{stock_code}_投资建议.md",
            mime="text/markdown",
        )

    with tabs[1]:
        st.markdown("<div class='af-card'>", unsafe_allow_html=True)
        st.markdown("## 🛡️ 风控结论")
        if isinstance(risk, dict):
            decision = risk.get("decision", "未知")
            reason = risk.get("reason", "未提供详细理由")
            badge = _badge(decision, fg=("#14532d" if "通过" in decision else "#991b1b"), bg=("#dcfce7" if "通过" in decision else "#fee2e2"))
            st.markdown(f"{badge}", unsafe_allow_html=True)
            st.markdown(reason)
        else:
            st.markdown(str(risk))
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[2]:
        st.info("下方“📈 回测候选策略详情”包含完整回测展示（Top3 曲线、徽章、参数与指标）。")

    with tabs[3]:
        st.markdown("<div class='af-card'>", unsafe_allow_html=True)
        st.markdown("## 🧠 AI 深度思考过程")
        if reasonings and state.get("config", {}).get("thinking_mode", True):
            for r in reasonings:
                st.markdown(f"{_badge(r.get('agent','Agent'), fg='#0f172a', bg='#e2e8f0')}", unsafe_allow_html=True)
                st.info(r.get("content", ""))
        else:
            st.info("未开启或未返回思考过程。")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # 4. 展示回测候选策略
    with st.expander("📈 回测候选策略详情"):
        quant_data = state.get("quant_data", {})
        candidates = quant_data.get("backtest_candidates", [])
        if candidates:
            st.write(f"**回测系统生成了 {len(candidates)} 个策略候选（含不同参数组合）**")

            top = candidates[:3]
            if top:
                tabs = st.tabs([f"{_strategy_icon(float(c.get('metrics', {}).get('sharpe', 0) or 0))} Top {i+1}" for i, c in enumerate(top)])
                for i, (tab, cand) in enumerate(zip(tabs, top), start=1):
                    with tab:
                        metrics = cand.get("metrics", {})
                        sharpe = float(metrics.get("sharpe", 0) or 0)
                        mdd = float(metrics.get("max_drawdown", 0) or 0)
                        title = cand.get("label") or cand.get("name")
                        st.markdown(f"### {i}. {title}<br>{_sharpe_badge(sharpe)}{_mdd_badge(mdd)}", unsafe_allow_html=True)

                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Sharpe", f"{sharpe:.2f}")
                        col2.metric("CAGR", f"{metrics.get('cagr', 0)*100:.2f}%")
                        col3.metric("MDD", f"{mdd*100:.2f}%")
                        col4.metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.2f}%")

                        curve = cand.get("curve") or []
                        if curve:
                            cdf = pd.DataFrame(curve)
                            if "dt" in cdf.columns:
                                cdf["dt"] = pd.to_datetime(cdf["dt"], errors="coerce")
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=cdf["dt"], y=cdf["equity"], mode="lines", name="Equity"))
                            fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
                            st.plotly_chart(fig, width="stretch", key=f"equity_top_{i}_{_keyify(title, sharpe, mdd)}")

                        with st.expander("📌 策略摘要"):
                            st.markdown(cand.get("summary", "暂无摘要"))

            st.divider()
            for i, cand in enumerate(candidates, start=1):
                metrics = cand.get("metrics", {})
                sharpe = float(metrics.get("sharpe", 0) or 0)
                mdd = float(metrics.get("max_drawdown", 0) or 0)
                title = cand.get("label") or cand.get("name")
                st.markdown(f"{_strategy_icon(sharpe)} <b>{i}. {title}</b> {_sharpe_badge(sharpe)}{_mdd_badge(mdd)}", unsafe_allow_html=True)

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("CAGR", f"{metrics.get('cagr', 0)*100:.2f}%")
                col2.metric("Win", f"{metrics.get('win_rate', 0)*100:.1f}%")
                col3.metric("Trades", f"{int(metrics.get('trade_count', 0) or 0)}")
                col4.metric("Turnover", f"{metrics.get('turnover', 0):.3f}")
                col5.metric("Vol", f"{metrics.get('volatility', 0)*100:.1f}%")

                with st.expander("📝 详情"):
                    if cand.get("params"):
                        st.markdown(_badge("Params", fg="#0f172a", bg="#e2e8f0") + f"<code>{cand.get('params')}</code>", unsafe_allow_html=True)
                    st.info(cand.get("summary", "暂无摘要"))
                    curve = cand.get("curve") or []
                    if curve:
                        cdf = pd.DataFrame(curve)
                        if "dt" in cdf.columns:
                            cdf["dt"] = pd.to_datetime(cdf["dt"], errors="coerce")
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=cdf["dt"], y=cdf["equity"], mode="lines", name="Equity"))
                        fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10))
                        st.plotly_chart(fig, width="stretch", key=f"equity_{i}_{_keyify(title, sharpe, mdd)}")
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
        "api_base": api_base if api_base else (os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"),
        "api_key": api_key if api_key else os.getenv("OPENAI_API_KEY"),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking_mode": thinking_mode,
        "backtest_lookback_days": backtest_lookback_days,
        "backtest_sector_days": backtest_sector_days,
        "backtest_initial_cash": backtest_initial_cash,
        "backtest_commission": backtest_commission,
        "backtest_slippage": backtest_slippage,
    }
    run_workflow(prompt, config_params)

if not api_key:
    st.info("💡 请在侧边栏填写 API Key 后开始分析。")
