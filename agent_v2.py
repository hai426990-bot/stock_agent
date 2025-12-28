import os
import re
import time
import datetime
import akshare as ak
import pandas as pd
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.graph import StateGraph, END

# ==========================================
# 1. 配置区域
# ==========================================



# 配置 LLM (OpenAI通用格式)
llm = ChatOpenAI(
    model="mimo-v2-flash", 
    openai_api_key="sk-sxn16csuu2v8d.....",
    openai_api_base="https://api.xiaomimimo.com/v1",
    temperature=0.3, # 保持一定的理性
    default_headers={"HTTP-Referer": "https://github.com/stock-agent"},
    extra_body={
        "thinking": {"type": "enable"}
    }
)

search_tool = DuckDuckGoSearchRun()

# ==========================================
# 2. 数据引擎 (AkShare + 兜底)
# ==========================================

def get_data_engine(symbol: str):
    """
    全能数据获取引擎：
    1. 识别 A股/美股。
    2. 优先通过 AkShare 获取清洗好的复权数据。
    3. 失败则自动回退到 Search 模式。
    """
    print(f"\n🔄 [数据引擎] 正在请求 {symbol} 数据 (源: 东方财富)...")
    
    try:
        df = pd.DataFrame()
        fund_data = {}
        data_source = "akshare"
        
        # --- A股逻辑 (6位数字) ---
        if re.match(r"^\d{6}$", symbol):
            print("   -> 识别为 A股，正在拉取行情...")
            # 获取历史行情 (前复权)
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime("%Y%m%d")
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
            
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            
            # 统一列名
            df.rename(columns={'日期': 'Date', '收盘': 'Close'}, inplace=True)
            
            # 获取实时基本面
            spot = ak.stock_zh_a_spot_em()
            target = spot[spot['代码'] == symbol]
            if not target.empty:
                row = target.iloc[0]
                fund_data = {
                    "最新价": row['最新价'],
                    "涨跌幅": f"{row['涨跌幅']}%",
                    "市盈率(动)": row['市盈率-动态'],
                    "市净率": row['市净率'],
                    "总市值": f"{row['总市值']/1e8:.2f}亿",
                    "换手率": f"{row['换手率']}%"
                }

        # --- 美股逻辑 (字母) ---
        else:
            print("   -> 识别为 美股/其他，正在尝试拉取...")
            # AkShare 美股接口 (需注意美股代码在不同源可能不同，这里尝试通用获取)
            # 为了稳定性，美股如果AkShare失败，非常容易触发兜底
            df = ak.stock_us_hist(symbol=symbol, period="daily", start_date="20240101", adjust="qfq")
            df.rename(columns={'日期': 'Date', '收盘': 'Close'}, inplace=True)
            fund_data = {"提示": "美股实时基本面请参考财报或下方舆情分析"}

        # --- 数据计算 (RSI/MACD) ---
        if df.empty:
            raise Exception("数据为空")

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp12 = df['Close'].ewm(span=12, adjust=False).mean()
        exp26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        
        print("✅ [数据引擎] AkShare 获取成功。")
        return df.tail(10).to_string(), str(fund_data), "source_akshare"

    except Exception as e:
        print(f"⚠️ [数据引擎] 接口调用遇到障碍 ({e})，切换至搜索引擎模式...")
        # 兜底逻辑：直接搜
        try:
            price_info = search_tool.run(f"{symbol} stock price history technical analysis today")
            fund_info = search_tool.run(f"{symbol} stock financials valuation revenue growth")
            return price_info, fund_info, "source_search_fallback"
        except:
            return "无法获取数据", "无法获取数据", "source_failed"

# ==========================================
# 3. Agent 节点定义
# ==========================================

class AgentState(TypedDict):
    ticker: str
    data_source: str
    price_data: str
    fundamental_data: str
    tech_analysis: str
    fund_analysis: str
    news_analysis: str
    risk_analysis: str
    final_decision: str

def data_node(state: AgentState):
    p, f, s = get_data_engine(state["ticker"])
    return {"price_data": p, "fundamental_data": f, "data_source": s}

# --- 修复后的节点 2: 技术分析师 ---
def tech_node(state: AgentState):
    print("📈 [技术分析] 分析趋势...")
    # 1. 使用 {price_data} 占位，不要直接 f-string
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一位技术分析专家。请根据数据（表格或文本）分析当前趋势、RSI位置及MACD动能。给出明确的[看涨/看跌/震荡]结论。"),
        ("human", "股票: {ticker}\n数据源: {source}\n数据:\n{price_data}")
    ])
    
    # 2. 通过 invoke 传入具体数据
    chain = prompt | llm
    res = chain.invoke({
        "ticker": state['ticker'],
        "source": state['data_source'],
        "price_data": state['price_data']
    })
    return {"tech_analysis": res.content}

# --- 修复后的节点 3: 基本面分析师 (报错源头) ---
def fund_node(state: AgentState):
    print("🏢 [基本面] 审计估值...")
    # 1. 使用 {fund_data} 占位
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是基本面专家。请评估公司估值水平(PE/PB)及财务健康度。给出[低估/合理/高估]评级。"),
        ("human", "股票: {ticker}\n财务数据:\n{fund_data}")
    ])
    
    # 2. 通过 invoke 传入数据，LangChain 会正确处理大括号
    chain = prompt | llm
    res = chain.invoke({
        "ticker": state['ticker'],
        "fund_data": state['fundamental_data']
    })
    return {"fund_analysis": res.content}

def news_node(state: AgentState):
    print("📰 [舆情] 检索新闻...")
    news = search_tool.run(f"{state['ticker']} stock news sentiment analysis today")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是舆情分析师。请总结3条最新关键新闻，并打分(-10悲观 ~ +10乐观)。"),
        ("human", f"新闻搜索结果:\n{news}")
    ])
    return {"news_analysis": llm.invoke(prompt.format_messages()).content}

def risk_node(state: AgentState):
    print("🛡️ [风控] 评估风险...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是首席风控官。基于以上分析，指出最大风险点，并建议止损位。"),
        ("human", f"技术:{state['tech_analysis']}\n基本面:{state['fund_analysis']}\n舆情:{state['news_analysis']}")
    ])
    return {"risk_analysis": llm.invoke(prompt.format_messages()).content}

def manager_node(state: AgentState):
    print("👨‍💼 [基金经理] 生成最终报告...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是对冲基金经理。请输出最终决策报告 (Markdown格式)。
        结构：
        # [股票代码] 投资决策报告
        ## 1. 核心决策 (BUY/SELL/HOLD)
        ## 2. 详细理由 (结合技术、基本面、舆情)
        ## 3. 风险提示
        ## 4. 交易计划 (建议仓位/止损)
        """),
        ("human", f"""
        数据源: {state['data_source']}
        技术面: {state['tech_analysis']}
        基本面: {state['fund_analysis']}
        舆情: {state['news_analysis']}
        风控: {state['risk_analysis']}
        """)
    ])
    return {"final_decision": llm.invoke(prompt.format_messages()).content}

# ==========================================
# 4. 构建图与执行
# ==========================================

workflow = StateGraph(AgentState)
workflow.add_node("data", data_node)
workflow.add_node("tech", tech_node)
workflow.add_node("fund", fund_node)
workflow.add_node("news", news_node)
workflow.add_node("risk", risk_node)
workflow.add_node("manager", manager_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "tech")
workflow.add_edge("tech", "fund")
workflow.add_edge("fund", "news")
workflow.add_edge("news", "risk")
workflow.add_edge("risk", "manager")
workflow.add_edge("manager", END)

app = workflow.compile()

def save_to_markdown(ticker, content):
    """保存结果到 MD 文件"""
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Report_{ticker}_{date_str}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename

if __name__ == "__main__":
    print("🚀 AI 股票 Agent 已启动")
    symbol = input("请输入股票代码 (如 600519): ").strip().upper()
    
    start_time = time.time()
    result = app.invoke({"ticker": symbol})
    end_time = time.time()
    
    # 终端打印摘要
    print("\n" + "="*50)
    print("✅ 分析完成，正在写入文件...")
    
    # 保存文件
    final_report = result["final_decision"]
    # 可以在文件里追加一些源数据详情
    full_content = f"{final_report}\n\n---\n**附录：原始分析数据**\n\n- 数据来源: {result['data_source']}\n- 耗时: {end_time - start_time:.2f}秒\n"
    
    filename = save_to_markdown(symbol, full_content)
    
    print(f"📄 报告已保存至: {os.path.abspath(filename)}")
    print("="*50)
    print("终端预览:\n")
    print(final_report)