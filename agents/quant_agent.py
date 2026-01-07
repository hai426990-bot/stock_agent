from tools.stock_data import get_stock_hist_data, get_stock_financial_indicator, get_stock_fund_flow, get_stock_industry_comparison, get_board_hist_data
from state import AgentState
import pandas as pd

def quant_agent_node(state: AgentState):
    """
    数据分析师：负责获取 K 线数据、财务指标及资金流向
    """
    stock_code = state["stock_code"]
    stock_name = state["stock_name"]
    is_sector = state.get("is_sector", False)
    
    # 检查是否有错误或中断信号
    if state.get("error") or state.get("interrupted"):
        return {"messages": []}
    
    print(f"--- 📊 数据分析师: 正在分析 {stock_name}({stock_code}) 的量化数据 ---")
    
    # 1. 获取历史数据
    try:
        if is_sector:
            df = get_board_hist_data(stock_name, board_type=state.get("sector_type", "industry"), days=150)
        else:
            df = get_stock_hist_data(stock_code, days=150)
        
        # 检查是否有错误或中断信号
        if state.get("error") or state.get("interrupted"):
            return {"messages": []}
    except Exception as e:
        print(f"获取历史数据失败: {e}")
        df = pd.DataFrame()
    
    # 板块分析跳过财务指标和资金流向排名（因为是整体分析）
    financials = {}
    fund_flow = {}
    industry_data = {}
    
    if not is_sector:
        # 2. 获取财务指标
        try:
            financials = get_stock_financial_indicator(stock_code)
            if not financials or "error" in financials:
                print(f"⚠️ 财务指标获取异常，使用默认值")
                financials = {
                    "warning": "财务指标数据暂不可用",
                    "数据状态": "缺失",
                    "建议": "建议人工复核财务数据"
                }
        except Exception as e:
            print(f"获取财务指标失败: {e}")
            financials = {
                "warning": f"获取财务指标失败: {str(e)[:50]}",
                "数据状态": "异常",
                "建议": "建议人工复核财务数据"
            }
        
        # 3. 获取资金流向
        try:
            fund_flow = get_stock_fund_flow(stock_code)
            if not fund_flow or "error" in fund_flow:
                print(f"⚠️ 资金流向获取异常，使用默认值")
                fund_flow = {
                    "代码": stock_code,
                    "warning": "资金流向数据暂不可用",
                    "数据状态": "缺失",
                    "建议": "建议人工复核资金流向数据"
                }
        except Exception as e:
            print(f"获取资金流向失败: {e}")
            fund_flow = {
                "代码": stock_code,
                "warning": f"获取资金流向失败: {str(e)[:50]}",
                "数据状态": "异常",
                "建议": "建议人工复核资金流向数据"
            }
        
        # 4. 获取行业对比数据
        try:
            industry_data = get_stock_industry_comparison(stock_code)
            if not industry_data or "error" in industry_data:
                print(f"⚠️ 行业对比数据获取异常，使用默认值")
                industry_data = {
                    "warning": "行业对比数据暂不可用",
                    "数据状态": "缺失",
                    "建议": "建议人工复核行业对比数据"
                }
        except Exception as e:
            print(f"获取行业对比失败: {e}")
            industry_data = {
                "warning": f"获取行业数据失败: {str(e)[:50]}",
                "数据状态": "异常",
                "建议": "建议人工复核行业对比数据"
            }
    
    if isinstance(df, pd.DataFrame) and not df.empty and len(df) >= 10:
        try:
            # 确保数据按日期升序
            df = df.sort_values('日期')
            
            # 1. 均线系统 (MA)
            df["MA5"] = df["收盘"].rolling(window=5).mean()
            df["MA10"] = df["收盘"].rolling(window=10).mean()
            df["MA20"] = df["收盘"].rolling(window=20).mean()
            df["MA60"] = df["收盘"].rolling(window=60).mean()
            
            # 2. 指数平滑异同平均线 (MACD)
            exp1 = df["收盘"].ewm(span=12, adjust=False).mean()
            exp2 = df["收盘"].ewm(span=26, adjust=False).mean()
            df["MACD"] = exp1 - exp2
            df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
            df["Hist"] = df["MACD"] - df["Signal"]
            
            # 3. 相对强弱指标 (RSI)
            delta = df["收盘"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            # 4. 布林带 (BOLL)
            df["BOLL_MID"] = df["收盘"].rolling(window=20).mean()
            df["BOLL_STD"] = df["收盘"].rolling(window=20).std()
            df["BOLL_UPPER"] = df["BOLL_MID"] + 2 * df["BOLL_STD"]
            df["BOLL_LOWER"] = df["BOLL_MID"] - 2 * df["BOLL_STD"]
            
            # 5. 随机指标 (KDJ)
            low_list = df["最低"].rolling(9, min_periods=9).min()
            high_list = df["最高"].rolling(9, min_periods=9).max()
            rsv = (df["收盘"] - low_list) / (high_list - low_list) * 100
            df["KDJ_K"] = rsv.ewm(com=2).mean()
            df["KDJ_D"] = df["KDJ_K"].ewm(com=2).mean()
            df["KDJ_J"] = 3 * df["KDJ_K"] - 2 * df["KDJ_D"]
            
            # 6. 成交量分析
            df["VMA5"] = df["成交量"].rolling(window=5).mean()
            df["VMA10"] = df["成交量"].rolling(window=10).mean()
            
            # 仅对基础列填充 NaN，保留技术指标的 NaN 以避免误导形态识别
            base_cols = ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]
            df[base_cols] = df[base_cols].fillna(0)
            
            vma5_last = df["VMA5"].iloc[-1] if not pd.isna(df["VMA5"].iloc[-1]) else 0
            volume_ratio = df["成交量"].iloc[-1] / vma5_last if vma5_last != 0 else 1
            
            # 7. 技术形态识别 (指标 + K线形态)
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            patterns = []
            # --- 指标类形态 ---
            if last_row["MA5"] > last_row["MA10"] > last_row["MA20"]:
                patterns.append("均线多头排列")
            if prev_row["MACD"] < prev_row["Signal"] and last_row["MACD"] > last_row["Signal"]:
                patterns.append("MACD 金叉")
            if prev_row["MACD"] > prev_row["Signal"] and last_row["MACD"] < last_row["Signal"]:
                patterns.append("MACD 死叉")
            if last_row["RSI"] > 75: patterns.append("RSI 超买 (警惕回调)")
            elif last_row["RSI"] < 25: patterns.append("RSI 超跌 (存在反弹需求)")
            
            if last_row["收盘"] > last_row["BOLL_UPPER"]: patterns.append("布林带上轨压力")
            elif last_row["收盘"] < last_row["BOLL_LOWER"]: patterns.append("布林带下轨支撑")

            # --- 经典 K 线形态 (基于最近两根蜡烛) ---
            body = last_row["收盘"] - last_row["开盘"]
            abs_body = abs(body)
            upper_shadow = last_row["最高"] - max(last_row["开盘"], last_row["收盘"])
            lower_shadow = min(last_row["开盘"], last_row["收盘"]) - last_row["最低"]
            
            prev_body = prev_row["收盘"] - prev_row["开盘"]
            
            # 1. 锤子线/倒锤子线 (底部信号)
            if lower_shadow > 2 * abs_body and upper_shadow < 0.1 * abs_body:
                patterns.append("锤子线 (潜在底部反转)")
            if upper_shadow > 2 * abs_body and lower_shadow < 0.1 * abs_body:
                patterns.append("倒锤子线 (潜在底部信号)")
                
            # 2. 十字星
            if abs_body < (last_row["最高"] - last_row["最低"]) * 0.1:
                patterns.append("十字星 (多空博弈激烈/变盘信号)")
                
            # 3. 看涨/看跌吞没
            if last_row["收盘"] > last_row["开盘"] and prev_row["收盘"] < prev_row["开盘"]:
                if last_row["收盘"] > prev_row["开盘"] and last_row["开盘"] < prev_row["收盘"]:
                    patterns.append("看涨吞没 (强力反转)")
            if last_row["收盘"] < last_row["开盘"] and prev_row["收盘"] > prev_row["开盘"]:
                if last_row["收盘"] < prev_row["开盘"] and last_row["开盘"] > prev_row["收盘"]:
                    patterns.append("看跌吞没 (强力压制)")

            # 4. 向上/向下跳空
            if last_row["最低"] > prev_row["最高"]:
                patterns.append("向上跳空缺口 (动能强劲)")
            if last_row["最高"] < prev_row["最低"]:
                patterns.append("向下跳空缺口 (恐慌抛售)")

            # --- 5. 量价协同分析 (专业进阶) ---
            # 计算 OBV (能量潮指标)
            df["OBV"] = (df["成交量"] * ((df["收盘"] > df["收盘"].shift(1)).astype(int) * 2 - 1)).fillna(0).cumsum()

            avg_vol = df["成交量"].tail(5).mean()
            price_change = (last_row["收盘"] - prev_row["收盘"]) / prev_row["收盘"]
            vol_change = (last_row["成交量"] - prev_row["成交量"]) / prev_row["成交量"]

            if price_change > 0.02 and last_row["成交量"] > avg_vol * 1.5:
                patterns.append("放量上涨 (趋势确认)")
            elif price_change > 0.02 and last_row["成交量"] < avg_vol * 0.7:
                patterns.append("缩量上涨 (动能不足/背离)")
            elif price_change < -0.02 and last_row["成交量"] > avg_vol * 1.5:
                patterns.append("放量下跌 (恐慌盘杀出)")
            elif price_change < -0.02 and last_row["成交量"] < avg_vol * 0.7:
                patterns.append("无量阴跌 (阴跌无底/警惕)")

            # OBV 趋势判断
            if df["OBV"].iloc[-1] > df["OBV"].iloc[-5]:
                patterns.append("OBV 能量潮上升 (资金持续流入)")
            
            # 8. 数据清洗 (防止 NaN/Inf 传递给大模型导致幻觉)
            def clean_value(val, name="指标"):
                if pd.isna(val) or val == float('inf') or val == float('-inf'):
                    return f"数据不足无法计算{name}"
                return round(float(val), 3)

            latest_price = last_row["收盘"]
            tech_indicators = {
                "latest_price": clean_value(latest_price, "现价"),
                "ma_system": {
                    "ma5": clean_value(last_row["MA5"], "5日均线"),
                    "ma10": clean_value(last_row["MA10"], "10日均线"),
                    "ma20": clean_value(last_row["MA20"], "20日均线"),
                    "ma60": clean_value(last_row["MA60"], "60日均线")
                },
                "macd": {
                    "diff": clean_value(last_row["MACD"], "MACD_DIF(12,26)"),
                    "dea": clean_value(last_row["Signal"], "MACD_DEA(9)"),
                    "hist": clean_value(last_row["Hist"], "MACD_HIST")
                },
                "rsi": clean_value(last_row["RSI"], "RSI(14日)"),
                "kdj": {
                    "k": clean_value(last_row["KDJ_K"], "KDJ_K(9日)"),
                    "d": clean_value(last_row["KDJ_D"], "KDJ_D(9日)"),
                    "j": clean_value(last_row["KDJ_J"], "KDJ_J(9日)")
                },
                "boll": {
                    "upper": clean_value(last_row["BOLL_UPPER"], "BOLL上轨(20日,2σ)"),
                    "mid": clean_value(last_row["BOLL_MID"], "BOLL中轨(20日)"),
                    "lower": clean_value(last_row["BOLL_LOWER"], "BOLL下轨(20日,2σ)")
                },
                "volume": {
                    "volume_ratio": clean_value(volume_ratio, "量比"),
                    "is_vol_expanding": bool(last_row["成交量"] > df["VMA5"].iloc[-1])
                },
                "identified_patterns": patterns,
                "change_pct": clean_value(last_row.get("涨跌幅", 0), "涨跌幅"),
                "fund_flow": fund_flow
            }
        except Exception as e:
            print(f"技术指标计算失败: {e}")
            import traceback
            traceback.print_exc()
            tech_indicators = {"error": f"指标计算失败: {e}", "fund_flow": fund_flow}
    else:
        tech_indicators = {"error": "无法获取历史数据", "fund_flow": fund_flow}
        
    # 整合财务和行业数据
    combined_quant_data = financials if isinstance(financials, dict) else {"info": financials}
    combined_quant_data["industry_comparison"] = industry_data

    return {
        "quant_data": combined_quant_data,
        "technical_indicators": tech_indicators,
        "sector_cons": state.get("sector_cons", []), # 保持原样传递
        "messages": [f"数据分析师完成了对 {stock_code} 的量化、行业对比及主力资金动向分析。"]
    }
