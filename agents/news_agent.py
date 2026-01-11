from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from tools.stock_data import get_stock_news, get_stock_report, get_board_news
from state import AgentState
import os

def news_agent_node(state: AgentState):
    """
    资讯侦察兵：专门利用 AkShare 获取 A 股专业资讯（新闻、研报）
    """
    stock_code = state["stock_code"]
    stock_name = state.get("stock_name", stock_code)
    is_sector = state.get("is_sector", False)
    
    # 检查是否有错误或中断信号
    if state.get("error") or state.get("interrupted"):
        return {"messages": []}
    
    print(f"--- 🕵️‍♂️ 资讯侦察兵: 正在分析 {stock_name}({stock_code}) 的专业金融资讯 ---")
    
    # 1. 获取专业金融新闻
    if is_sector:
        sector_type = state.get("sector_type", "industry")
        financial_news = get_board_news(stock_name, sector_type)
        profit_forecast = [] # 板块没有个股盈利预测
    else:
        financial_news = get_stock_news(stock_code)
        profit_forecast = get_stock_report(stock_code)
    
    # 从 state 中获取独立配置
    config = state.get("config", {})
    model_name = config.get("model_name", "gpt-3.5-turbo")
    temperature = config.get("temperature", 0.5)
    max_tokens = config.get("max_tokens", 4096)
    api_base = config.get("api_base", "https://api.openai.com/v1")
    api_key = config.get("api_key")
    
    if not isinstance(api_key, str) or not api_key:
        return {
            "news_analysis": "Error: Invalid API Key",
            "sentiment_score": 0.0,
            "news_items": financial_news
        }

    # 深度思考模式配置
    model_kwargs = {}
    # NVIDIA/OpenAI 接口通常不需要显式设置 include_reasoning，
    # 且该参数不是 OpenAI 标准参数，会导致部分 Provider 报错。
    # 如果 Provider 支持，推理内容通常会自动包含在响应中。

    llm = ChatOpenAI(
        model=model_name, 
        temperature=temperature, 
        max_tokens=max_tokens,
        base_url=api_base,
        api_key=api_key,
        model_kwargs=model_kwargs
    )
    parser = JsonOutputParser()
    
    prompt = ChatPromptTemplate.from_template("""
    ### 角色定义
    你是一位资深的金融资讯分析专家，拥有 15 年 A 股市场研究经验。你擅长从海量碎片化信息中捕捉核心价值，并能准确判断资讯对股价的潜在影响方向及程度。
    
    ### 任务描述
    分析关于股票/板块【{stock_name}】的最新财务新闻和研报盈利预测，提取核心洞察并进行情感量化。
    
    ### 输入数据
    ---
    【最新财务新闻】: 
    {financial_news}
    
    【研报盈利预测】: 
    {profit_forecast}
    ---
    
    ### 分析要求
    1. **信噪比过滤**: 忽略无关的广告、重复性信息或陈旧数据。
    2. **核心摘要**: 总结对基本面有重大影响的事件。
    3. **情感评分逻辑**: 
       - 1.0: 极大利好 (如重组、核心大客户、业绩暴增)
       - 0.5: 较大利好 (如行业回暖、小额合同、一般利好传闻)
       - 0.0: 中性 (常规变动、已澄清的传闻、无重大消息)
       - -0.5: 较大利空 (减持、业绩微跌、一般负面传闻)
       - -1.0: 极大利空 (造假、退市、核心业务崩塌)
    4. **评价倾向**: 
       - 如果有明确的利好/利空（如“字节跳动供应商”、“中标”、“业绩预增”等），请给出 non-zero 的评分。
       - 只有在真正缺乏资讯、或者利好利空完全抵消时，才给出 0.0 分。
    5. **数据缺失处理**: 若输入数据为空或仅包含无关信息，请在 `analysis` 中诚实说明：“当前暂无关于该标的的深度资讯或研报更新”，并将 `sentiment_score` 设为 0.0。
    
    ### 输出格式
    {format_instructions}
    """)
    
    # 手动渲染 prompt
    prompt_str = prompt.format(
        stock_name=stock_name,
        financial_news=financial_news if financial_news else "【暂无可用数据】",
        profit_forecast=profit_forecast if profit_forecast else "【暂无可用数据】",
        format_instructions=parser.get_format_instructions()
    )
    
    try:
        raw_res = llm.invoke(prompt_str)
        
        # 提取思考过程 (针对 DeepSeek 等模型)
        reasoning = raw_res.additional_kwargs.get("reasoning_content", "")
        
        # 解析 JSON 结果
        try:
            response = parser.parse(raw_res.content)
            analysis = response.get("analysis", "")
            
            # 检查分析是否有效
            if not analysis or len(analysis) < 20:
                analysis = "资讯摘要解析失败：返回内容过短或为空"
                sentiment_score = 0.0
                parse_success = False
            elif "暂无可用数据" in analysis or "暂无深度资讯" in analysis or "解析分析内容失败" in analysis:
                analysis = "资讯摘要解析失败：暂无可用数据"
                sentiment_score = 0.0
                parse_success = False
            else:
                parse_success = True
                # 规范化 sentiment_score
                try:
                    sentiment_score = float(response.get("sentiment_score", 0.0))
                    sentiment_score = max(-1.0, min(1.0, sentiment_score)) # Clamp to [-1, 1]
                except (ValueError, TypeError):
                    sentiment_score = 0.0
        except Exception as pe:
            print(f"JSON 解析失败，尝试从文本提取: {pe}")
            # 简单的回退逻辑
            analysis = "资讯摘要解析失败：JSON 格式错误"
            sentiment_score = 0.0
            parse_success = False

        return {
            "news_analysis": analysis,
            "sentiment_score": sentiment_score,
            "news_items": financial_news,
            "news_parse_success": parse_success,
            "reasoning_content": [{"agent": "资讯侦察兵", "content": reasoning if reasoning else "未获取到思考过程"}]
        }
    except Exception as e:
        error_msg = f"资讯侦察兵运行出错: {str(e)}"
        print(f"💥 {error_msg}")
        return {
            "news_analysis": "获取分析失败",
            "sentiment_score": 0.0,
            "news_items": financial_news,
            "news_parse_success": False,
            "error": error_msg
        }
