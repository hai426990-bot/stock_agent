import streamlit as st
import pandas as pd
import os
import json
import hashlib
import shutil
import time
from datetime import datetime, timedelta
from functools import wraps
from graph import create_alpha_flow_graph
from tools.stock_data import (
    search_stock_code, 
    get_stock_hist_data, 
    search_board_info, 
    get_board_hist_data, 
    get_board_cons, 
    get_cache_status, 
    clear_akshare_cache, 
    get_market_indices, 
    get_market_hot_sectors, 
    get_market_sentiment
)
from tools.news_fetcher import get_10jqka_news
from tools.constituents import top_constituents
import plotly.graph_objects as go
from pathlib import Path
from config import get_config_manager, get_config, set_runtime_config

# 性能监控装饰器
def log_performance(func):
    """记录函数执行时间"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            print(f"⏱️ {func.__name__} 执行时间: {elapsed:.2f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ {func.__name__} 执行失败 (耗时 {elapsed:.2f}秒): {e}")
            raise
    return wrapper

config_manager = get_config_manager()

page_title = config_manager.get("web.page_title", "AlphaFlow 智能投资决策系统")
page_icon = config_manager.get("web.page_icon", "📈")
layout = config_manager.get("web.layout", "wide")
initial_sidebar_state = config_manager.get("web.initial_sidebar_state", "expanded")

st.set_page_config(
    page_title=page_title,
    page_icon=page_icon,
    layout=layout,
    initial_sidebar_state=initial_sidebar_state
)

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

@st.cache_data(ttl=300, show_spinner="正在加载市场数据...")
@log_performance
def render_market_dashboard():
    """
    渲染市场全览仪表盘（缓存 5 分钟）
    """
    st.markdown("### 🌏 A股市场全览")
    
    # 1. 指数行情
    indices = get_market_indices()
    if indices:
        cols = st.columns(len(indices))
        for i, idx in enumerate(indices):
            with cols[i]:
                st.metric(
                    label=idx['name'],
                    value=f"{idx['price']}",
                    delta=f"{idx['change_pct']}%"
                )
    else:
        st.info("正在获取实时指数行情...")

    st.divider()
    
    # 2. 市场情绪与热门板块
    c1, c2 = st.columns([0.4, 0.6])
    
    with c1:
        st.markdown("**🌡️ 市场情绪分布**")
        sentiment = get_market_sentiment()
        if sentiment:
            up = sentiment.get("上涨家数", 0)
            down = sentiment.get("下跌家数", 0)
            flat = 5300 - up - down # Approx total
            
            # Simple bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=['家数'], x=[up], name='上涨', orientation='h', marker_color='#ef4444'
            ))
            fig.add_trace(go.Bar(
                y=['家数'], x=[flat], name='平盘', orientation='h', marker_color='#94a3b8'
            ))
            fig.add_trace(go.Bar(
                y=['家数'], x=[down], name='下跌', orientation='h', marker_color='#22c55e'
            ))
            fig.update_layout(barmode='stack', height=120, margin=dict(l=0, r=0, t=0, b=0), 
                             xaxis=dict(showticklabels=False), yaxis=dict(visible=False),
                             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
            c1_sub = st.columns(2)
            c1_sub[0].metric("涨停", sentiment.get("涨停家数", "-"))
            c1_sub[1].metric("跌停", sentiment.get("跌停家数", "-"))
            st.caption(f"市场宽度: {sentiment.get('市场宽度', 0)*100:.1f}% ({sentiment.get('情绪描述', '')})")
        else:
            st.write("数据加载中...")

    with c2:
        st.markdown("**🔥 领涨行业板块**")
        hot_sectors = get_market_hot_sectors(limit=5)
        if hot_sectors:
            # Create a clean table
            df_hot = pd.DataFrame(hot_sectors)
            st.dataframe(
                df_hot,
                column_config={
                    "板块名称": "板块",
                    "涨跌幅": st.column_config.NumberColumn("涨幅", format="%.2f%%"),
                    "领涨股票": "领涨股",
                    "最新价": st.column_config.NumberColumn("板块指数", format="%.0f")
                },
                hide_index=True,
                use_container_width=True,
                height=200
            )
        else:
            st.write("数据加载中...")

    # 3. 同花顺新闻实时动态
    st.divider()
    st.markdown("**📰 同花顺新闻实时动态**")
    
    try:
        news_list = get_10jqka_news(limit=8)
        
        if news_list:
            for news in news_list:
                with st.container():
                    # 时间和标题
                    st.markdown(f"<span style='color:#64748b;font-size:12px'>{news['time']}</span> <strong>{news['title']}</strong>", unsafe_allow_html=True)
                    
                    # 显示相关股票
                    if news['stocks']:
                        st.caption(f"📌 相关股票: {', '.join(news['stocks'])}")
                    
                    # 内容
                    st.caption(news['content'])
                    st.divider()
        else:
            st.info("正在获取同花顺新闻...")
    except Exception as e:
        st.warning(f"同花顺新闻加载失败: {str(e)[:50]}")

    

def load_model_cache():
    try:
        if not MODEL_CACHE_FILE.exists():
            return None
        with open(MODEL_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        cache_time = datetime.fromisoformat(cache_data.get("cache_time", ""))
        if datetime.now() - cache_time > timedelta(hours=24):
            return None
        return cache_data.get("model_name")
    except Exception:
        return None

def save_model_cache(model_name: str):
    try:
        cache_data = {
            "model_name": model_name,
            "cache_time": datetime.now().isoformat()
        }
        with open(MODEL_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
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
if "sector_constituent_analyses" not in st.session_state:
    st.session_state.sector_constituent_analyses = {}

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
            if st.button("🗑️ 清空全部历史", key="clear_all_history", use_container_width=True):
                clear_all_history()
                st.rerun()
            st.divider()
            
            for h_file in history_files[:20]:
                try:
                    with open(os.path.join(HISTORY_DIR, h_file), "r", encoding="utf-8") as f:
                        h_data = json.load(f)
                        col1, col2 = st.columns([0.8, 0.2])
                        with col1:
                            if st.button(f"{h_data['date']}\n{h_data['stock_name']}", key=f"btn_{h_file}", use_container_width=True):
                                st.session_state.messages = [{"role": "assistant", "content": h_data['report']}]
                                st.rerun()
                        with col2:
                            if st.button("❌", key=f"del_{h_file}", help="删除此记录", use_container_width=True):
                                delete_history(h_file)
                                st.rerun()
                except Exception:
                    pass

    with st.expander("📊 回测候选策略", expanded=True):
        state = st.session_state.workflow_state or {}
        quant_data = state.get("quant_data", {})
        candidates = quant_data.get("backtest_candidates", [])
        if candidates:
            st.write(f"**找到 {len(candidates)} 个候选策略**")
            for i, cand in enumerate(candidates[:5]):
                metrics = cand.get('metrics', {})
                with st.container():
                    sharpe = float(metrics.get("sharpe", 0) or 0)
                    mdd = float(metrics.get("max_drawdown", 0) or 0)
                    title = cand.get("label") or cand.get("name")
                    st.markdown(f"{_strategy_icon(sharpe)} <b>{i+1}. {title}</b><br>{_sharpe_badge(sharpe)}{_mdd_badge(mdd)}", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("CAGR", f"{metrics.get('cagr', 0)*100:.2f}%")
                    c2.metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.2f}%")
                    c3.metric("MDD", f"{metrics.get('max_drawdown', 0)*100:.2f}%")
                    if i < len(candidates[:5]) - 1:
                        st.divider()
        else:
            st.info("暂无可用的候选策略数据")

    with st.expander("🗄️ 缓存状态", expanded=True):
        current = st.session_state.get("current_stock") or {}
        stock_code = current.get("code")
        st.json(get_cache_status(stock_code))

    with config_tab:
        default_model = config_manager.get("model_name", "gpt-4o")
        supported_models = config_manager.get("supported_models", ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "mimo-v2-flash"])
        common_models = supported_models
        if default_model not in common_models:
            common_models.insert(0, default_model)
        
        try:
            default_index = common_models.index(default_model)
        except ValueError:
            default_index = 0
        
        selected_model = st.selectbox("选择或输入分析模型", common_models, index=default_index)
        custom_model = st.text_input("自定义模型名称 (可选)", value=selected_model)
        model_to_use = custom_model if custom_model else selected_model
        
        st.divider()
        st.subheader("🔑 API 凭据配置")
        api_base = st.text_input("API Base URL", value=config_manager.get("api_base", "https://api.openai.com/v1"))
        api_key = st.text_input("API Key", value=config_manager.get("api_key", ""), type="password")
        
        if not api_key:
            st.warning("⚠️ 请输入 API Key")
        
        temperature = st.slider("Temperature", 0.0, 1.0, config_manager.get("llm.temperature", 0.3), 0.1)
        max_tokens = st.select_slider("Max Tokens", options=[1024, 2048, 4096, 8192, 16384], value=config_manager.get("llm.max_tokens", 8192))
        thinking_mode = st.toggle("开启深度思考模式", value=config_manager.get("llm.thinking_mode", True))

        st.divider()
        st.subheader("📊 回测参数")
        bt_days = st.number_input("回测回溯天数", min_value=30, max_value=3650, value=config_manager.get("backtest.days", 365))
        bt_cash = st.number_input("初始资金", min_value=1000.0, value=config_manager.get("backtest.cash", 100000.0))

        st.divider()
        if st.button("💾 保存配置", use_container_width=True, type="primary"):
            user_config = {
                "model_name": model_to_use,
                "api_base": api_base,
                "api_key": api_key,
                "llm": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "thinking_mode": thinking_mode
                },
                "backtest": {
                    "days": bt_days,
                    "cash": bt_cash
                }
            }
            config_manager.save_user_config(user_config)
            st.success("✅ 配置已保存！")
            st.rerun()

        if st.button("🧹 清理本地缓存", use_container_width=True):
            clear_akshare_cache(ttl_seconds=0)
            st.success("已清理")
        
        if st.button("🗑️ 清除当前对话", key="clear_chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.workflow_state = None
            st.rerun()

st.title("📈 AlphaFlow 智能投资决策系统")
st.caption("基于 LangGraph 的多智能体协作 A 股决策平台")

# 如果存在 workflow_state，显示完整的报告界面
if st.session_state.workflow_state:
    display_results(st.session_state.workflow_state)
else:
    # 市场仪表盘
    if not st.session_state.messages:
        render_market_dashboard()
    
    # 展示聊天历史
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 处理工作流逻辑
@st.cache_data(ttl=3600, show_spinner=False)
def _get_entity_info(input_str):
    if input_str.isdigit() and len(input_str) == 6:
        return input_str, input_str, False, "", []
    board_info = search_board_info(input_str)
    if board_info:
        return board_info["code"], board_info["name"], True, board_info["type"], get_board_cons(board_info["name"], board_info["type"])
    return search_stock_code(input_str) + (False, "", [])

@log_performance
def run_workflow(input_str, config_params):
    if not config_params.get("api_key"):
        st.error("❌ 未配置 API Key")
        return

    with st.status("🔍 正在检索信息...", expanded=True) as status:
        stock_code, stock_name, is_sector, sector_type, sector_cons = _get_entity_info(input_str)
        if not stock_code:
            st.error(f"未找到: {input_str}")
            return
        st.session_state.current_stock = {"code": stock_code, "name": stock_name, "is_sector": is_sector}
        status.update(label=f"✅ 已找到: {stock_name} ({stock_code})", state="complete")

    with st.status("🚀 AlphaFlow 协作中...", expanded=True) as status:
        initial_state = {
            "stock_code": stock_code, "stock_name": stock_name, "is_sector": is_sector,
            "sector_type": sector_type, "sector_cons": sector_cons,
            "news_items": [], "news_analysis": "", "sentiment_score": 0.0,
            "quant_data": {"backtest_candidates": []}, "technical_indicators": {},
            "strategy_report": "", "risk_assessment": "", "messages": [],
            "revision_needed": False, "human_approval": False, "count": 0,
            "error": "", "consecutive_failures": 0, "config": config_params
        }
        try:
            final_state = initial_state
            for output in st.session_state.app.stream(initial_state):
                for node_name, state_update in output.items():
                    final_state.update(state_update)
                    st.write(f"✔️ {node_name} 处理完成")
            status.update(label="✅ 分析完成！", state="complete", expanded=True)
            st.session_state.workflow_state = final_state
            display_results(final_state)
        except Exception as e:
            st.error(f"❌ 运行失败: {str(e)}")

@log_performance
def display_results(state):
    inject_global_css()
    report = state.get("strategy_report", "未生成")
    risk = state.get("risk_assessment", "未审核")
    stock_code = state.get("stock_code")
    stock_name = state.get("stock_name")
    is_sector = state.get("is_sector", False)
    sentiment = float(state.get("sentiment_score", 0.0) or 0.0)
    
    quant_data = state.get("quant_data", {})
    market_sent = quant_data.get("market_sentiment", {})
    sent_desc = market_sent.get("情绪描述", "未知")
    breadth = market_sent.get("市场宽度", 0.5)

    st.markdown(f"""
        <div class="af-hero">
          <div style="display:flex;justify-content:space-between;align-items:flex-end">
            <div>
              <div class="af-title">AlphaFlow 报告 · {stock_name} ({stock_code})</div>
              <div class="af-subtitle">{'板块' if is_sector else '股票'} · {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
            </div>
            <div>
              {_badge('全市场情绪', fg='#0f172a')} {_badge(sent_desc, bg='#dcfce7' if breadth>0.6 else '#fee2e2' if breadth<0.4 else '#e2e8f0')}
              {_badge('资讯情绪', fg='#0f172a')} {_badge(f'{sentiment:+.2f}', bg='#dcfce7' if sentiment>0.15 else '#fee2e2' if sentiment<-0.15 else '#e2e8f0')}
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    st.divider()

    tabs = st.tabs(["🧾 报告正文", "🛡️ 风控结论", "📊 基本面/估值", "📈 回测策略", "📰 财联社电报"])
    with tabs[0]:
        if report and report != "未生成":
            st.markdown(report)
        else:
            st.warning("报告正文未生成或为空")
    with tabs[1]:
        st.json(risk)
    with tabs[2]:
        val = quant_data.get("valuation_history", {})
        if val:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("PE", f"{val.get('latest_pe', 0):.2f}")
            c2.metric("PE 分位", f"{val.get('pe_percentile', 0):.1f}%")
            c3.metric("PB", f"{val.get('latest_pb', 0):.2f}")
            c4.metric("PB 分位", f"{val.get('pb_percentile', 0):.1f}%")
        else:
            st.info("暂无估值数据")
    with tabs[3]:
        candidates = quant_data.get("backtest_candidates", [])
        state = st.session_state.workflow_state or {}
        stock_code = state.get("stock_code")
        
        # 获取回测配置的天数
        config = state.get("config", {})
        backtest_days = config.get("backtest_lookback_days", 365)
        
        if not candidates:
            st.info("暂无回测策略数据")
        else:
            st.caption(f"📊 回测周期: 最近 {backtest_days} 天")
            
            for i, cand in enumerate(candidates[:3]):
                with st.expander(f"📊 {i+1}. {cand.get('label')}", expanded=True):
                    metrics = cand.get("metrics", {})
                    signals = cand.get("signals", [])
                    buy_count = cand.get("buy_count", 0)
                    sell_count = cand.get("sell_count", 0)
                    
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("Sharpe", f"{metrics.get('sharpe', 0):.2f}")
                    c2.metric("CAGR", f"{metrics.get('cagr', 0)*100:.1f}%")
                    c3.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0)*100:.1f}%")
                    c4.metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.1f}%")
                    c5.metric("🟢 Buy Signals", f"{buy_count}")
                    c6.metric("🔴 Sell Signals", f"{sell_count}")
                    
                    if signals:
                        signal_df = pd.DataFrame(signals)
                        signal_df["date"] = pd.to_datetime(signal_df["date"])
                        signal_df["type_display"] = signal_df["type"].apply(lambda x: "🟢 买入" if x == "BUY" else "🔴 卖出")
                        
                        col_chart, col_table = st.columns([2, 1])
                        
                        with col_chart:
                            from tools.stock_data import get_stock_hist_data
                            try:
                                # 使用配置中的回测天数，但限制最大值为365天以提升渲染性能
                                lookback_days = min(backtest_days, 365)
                                price_data = get_stock_hist_data(stock_code, days=lookback_days)
                                
                                if not price_data.empty:
                                    # 转换中文列名为英文列名
                                    price_data = price_data.rename(columns={
                                        "日期": "dt",
                                        "开盘": "open",
                                        "最高": "high",
                                        "最低": "low",
                                        "收盘": "close",
                                        "成交量": "volume"
                                    })
                                    price_data["dt"] = pd.to_datetime(price_data["dt"])
                        
                                    fig = go.Figure()
                                    
                                    fig.add_trace(go.Candlestick(
                                        x=price_data["dt"],
                                        open=price_data["open"],
                                        high=price_data["high"],
                                        low=price_data["low"],
                                        close=price_data["close"],
                                        name="K线"
                                    ))
                                    
                                    buys = signal_df[signal_df["type"] == "BUY"]
                                    sells = signal_df[signal_df["type"] == "SELL"]
                        
                                if not buys.empty:
                                    fig.add_trace(go.Scatter(
                                        x=buys["date"],
                                        y=buys["price"],
                                        mode="markers",
                                        marker=dict(symbol="triangle-down", size=12, color="#22c55e"),
                                        name="买入信号"
                                    ))
                        
                                if not sells.empty:
                                    fig.add_trace(go.Scatter(
                                        x=sells["date"],
                                        y=sells["price"],
                                        mode="markers",
                                        marker=dict(symbol="triangle-up", size=12, color="#ef4444"),
                                        name="卖出信号"
                                    ))
                                    
                                    fig.update_layout(
                                        title=f"{cand.get('label')} - 买卖信号 (最近{lookback_days}天)",
                                        xaxis_title="日期",
                                        yaxis_title="价格",
                                        height=400,
                                        template="plotly_white",
                                        xaxis_rangeslider_visible=False
                                    )
                                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                                else:
                                    st.caption("暂无价格数据")
                            except Exception as e:
                                st.caption(f"图表数据获取失败: {str(e)[:50]}")
                    
                    with col_table:
                        st.markdown("**📋 信号列表**")
                        table_df = signal_df.copy()
                        table_df["date"] = table_df["date"].dt.strftime("%Y-%m-%d")
                        st.dataframe(
                            table_df,
                            column_config={
                                "date": "日期",
                                "type_display": "类型",
                                "price": st.column_config.NumberColumn("价格", format="%.2f")
                            },
                            hide_index=True,
                            height=300
                        )
    
    with tabs[4]:
        # 同花顺新闻标签页
        telegraph_analysis = state.get("telegraph_analysis", {})
        telegraph_news = state.get("telegraph_news", [])
        
        # 显示分析结果
        if telegraph_analysis:
            st.markdown("### 📊 市场动态分析")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("市场情绪", telegraph_analysis.get("market_sentiment", "未知"))
            col2.metric("重要事件", f"{len(telegraph_analysis.get('important_events', []))} 个")
            col3.metric("投资机会", f"{len(telegraph_analysis.get('opportunities', []))} 个")
            
            st.divider()
            
            # 显示摘要
            summary = telegraph_analysis.get("summary", "")
            if summary:
                st.markdown(f"**📝 总体摘要**\n\n{summary}")
            
            # 显示重要事件
            important_events = telegraph_analysis.get("important_events", [])
            if important_events:
                st.markdown("### 🔔 重要事件")
                for event in important_events:
                    impact = event.get("impact", "中性")
                    impact_color = "#dcfce7" if impact == "正面" else "#fee2e2" if impact == "负面" else "#e2e8f0"
                    st.markdown(f"<span style='background:{impact_color};padding:2px 8px;border-radius:4px;font-size:12px'>{impact}</span> **{event.get('title', '无标题')}**", unsafe_allow_html=True)
                    st.caption(event.get("description", ""))
                    st.divider()
            
            # 显示投资机会
            opportunities = telegraph_analysis.get("opportunities", [])
            if opportunities:
                st.markdown("### 💡 投资机会")
                for opp in opportunities:
                    st.markdown(f"- {opp}")
        
        # 显示新闻列表
        if telegraph_news:
            st.markdown("### 📰 实时新闻")
            for news in telegraph_news[:15]:
                with st.container():
                    # 时间和标题
                    st.markdown(f"<span style='color:#64748b;font-size:12px'>{news['time']}</span> <strong>{news['title']}</strong>", unsafe_allow_html=True)
                    
                    # 显示新闻内容
                    st.caption(news['content'])
                    
                    # 显示专业评论（如果有）
                    if 'analysis' in news and news['analysis']:
                        analysis = news['analysis']
                        
                        # 显示事件类型和影响
                        event_type = analysis.get('event_type', '其他')
                        impact = analysis.get('impact', '中性')
                        sentiment = analysis.get('sentiment', '中性')
                        
                        # 设置颜色
                        impact_color = {
                            '正面': '#dcfce7',
                            '负面': '#fee2e2',
                            '中性': '#f1f5f9'
                        }.get(impact, '#f1f5f9')
                        
                        impact_text_color = {
                            '正面': '#166534',
                            '负面': '#991b1b',
                            '中性': '#475569'
                        }.get(impact, '#475569')
                        
                        # 标签显示
                        st.markdown(
                            f"<div style='display:flex;gap:8px;margin:8px 0'>"
                            f"<span style='background:#e0e7ff;color:#3730a3;padding:2px 8px;border-radius:4px;font-size:12px'>{event_type}</span>"
                            f"<span style='background:{impact_color};color:{impact_text_color};padding:2px 8px;border-radius:4px;font-size:12px'>{impact}</span>"
                            f"<span style='background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:12px'>{sentiment}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        
                        # 显示专业评论
                        comment = analysis.get('comment', '')
                        if comment:
                            st.markdown(f"**💡 专业评论**\n\n{comment}")
                        
                        # 显示投资机会
                        opportunities = analysis.get('opportunities', [])
                        if opportunities:
                            st.markdown("**🎯 投资机会**")
                            for opp in opportunities:
                                st.markdown(f"- {opp}")
                        
                        # 显示风险提示
                        risks = analysis.get('risks', [])
                        if risks:
                            st.markdown("**⚠️ 风险提示**")
                            for risk in risks:
                                st.markdown(f"- {risk}")
                    
                    st.divider()
        else:
            st.info("暂无财联社电报数据")

    st.session_state.messages.append({"role": "assistant", "content": report})
    save_history(stock_name, stock_code, report)

if prompt := st.chat_input("请输入股票代码或名称", disabled=not api_key):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    config = {
        "model_name": model_to_use, "api_base": api_base, "api_key": api_key,
        "temperature": temperature, "max_tokens": max_tokens, "thinking_mode": thinking_mode,
        "backtest_lookback_days": bt_days, "backtest_initial_cash": bt_cash
    }
    run_workflow(prompt, config)