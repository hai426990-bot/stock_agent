from tools.stock_data import get_stock_financial_indicator, get_stock_fund_flow, get_stock_industry_comparison, get_board_hist_data
from state import AgentState
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from backtest.data import DataManager
from backtest.strategy import STRATEGY_REGISTRY
from backtest.engine import VectorizedEngine
from backtest.analytics import PerformanceAnalytics
from backtest.persistence import BacktestPersistence

def _hash_ohlcv(df: pd.DataFrame) -> str:
    cols = [c for c in ["dt", "open", "high", "low", "close", "volume", "adj_close"] if c in df.columns]
    if df.empty or not cols:
        return ""
    try:
        hashed = pd.util.hash_pandas_object(df[cols], index=True).values.tobytes()
        return hashlib.sha256(hashed).hexdigest()
    except Exception:
        return ""

def _format_params(params: dict) -> str:
    if not params:
        return ""
    parts = []
    for key, value in sorted(params.items()):
        if isinstance(value, float):
            parts.append(f"{key}={value:g}")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)

def _fetch_financials(stock_code):
    """并行获取财务指标"""
    try:
        result = get_stock_financial_indicator(stock_code)
        if not result or "error" in result:
            return {
                "warning": "财务指标数据暂不可用",
                "数据状态": "缺失",
                "建议": "建议人工复核财务数据"
            }
        return result
    except Exception as e:
        return {
            "warning": f"获取财务指标失败: {str(e)[:50]}",
            "数据状态": "异常",
            "建议": "建议人工复核财务数据"
        }

def _fetch_fund_flow(stock_code):
    """并行获取资金流向"""
    try:
        result = get_stock_fund_flow(stock_code)
        if not result or "error" in result:
            return {
                "代码": stock_code,
                "warning": "资金流向数据暂不可用",
                "数据状态": "缺失",
                "建议": "建议人工复核资金流向数据"
            }
        return result
    except Exception as e:
        return {
            "代码": stock_code,
            "warning": f"获取资金流向失败: {str(e)[:50]}",
            "数据状态": "异常",
            "建议": "建议人工复核资金流向数据"
        }

def _fetch_industry_data(stock_code):
    """并行获取行业对比数据"""
    try:
        result = get_stock_industry_comparison(stock_code)
        if not result or "error" in result:
            return {
                "warning": "行业对比数据暂不可用",
                "数据状态": "缺失",
                "建议": "建议人工复核行业对比数据"
            }
        return result
    except Exception as e:
        return {
            "warning": f"获取行业数据失败: {str(e)[:50]}",
            "数据状态": "异常",
            "建议": "建议人工复核行业对比数据"
        }

def _fetch_valuation_history(stock_code):
    """并行获取估值历史"""
    from tools.stock_data import get_stock_valuation_history
    try:
        return get_stock_valuation_history(stock_code)
    except Exception as e:
        print(f"获取估值历史失败: {e}")
        return {}

def _fetch_market_sentiment():
    """并行获取市场情绪"""
    from tools.stock_data import get_market_sentiment
    try:
        return get_market_sentiment()
    except Exception as e:
        print(f"获取市场情绪失败: {e}")
        return {}

def quant_agent_node(state: AgentState):
    """
    数据分析师：负责获取 K 线数据、财务指标及资金流向，并运行量化回测。
    """
    stock_code = state["stock_code"]
    stock_name = state.get("stock_name", stock_code)
    is_sector = state.get("is_sector", False)
    
    # 检查是否有错误信号
    if state.get("error"):
        return {"messages": [], "consecutive_failures": state.get("consecutive_failures", 0)}
    
    print(f"--- 📊 数据分析师: 正在分析 {stock_name}({stock_code}) 的量化数据 ---")
    
    # 1. 获取历史数据 (使用新的 DataManager 以统一 Schema)
    try:
        config = state.get("config", {})
        lookback_days = int(config.get("backtest_lookback_days", 365))
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")

        data_manager = DataManager()
        # 统一获取最近一年的数据进行回测，并包含财务与估值指标以支持复杂策略
        df = data_manager.get_data(stock_code, start_date=start_date, add_indicators=not is_sector)
        
        if df.empty and is_sector:
             # 如果是板块，回退到原有逻辑获取数据
             sector_days = int(config.get("backtest_sector_days", 252))
             df = get_board_hist_data(stock_name, board_type=state.get("sector_type", "industry"), days=sector_days)
             # 手动转换 schema
             df = df.rename(columns={"日期": "dt", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
             df["dt"] = pd.to_datetime(df["dt"])
             df["adj_close"] = df["close"]
        
        # 检查是否有错误信号
        if state.get("error"):
            return {"messages": [], "consecutive_failures": state.get("consecutive_failures", 0)}
    except Exception as e:
        print(f"获取历史数据失败: {e}")
        df = pd.DataFrame()

    # 板块分析跳过财务指标和资金流向排名（因为是整体分析）
    financials = {}
    fund_flow = {}
    industry_data = {}
    valuation_history = {}
    market_sentiment = {}
    
    # 使用多线程并行获取数据
    print(f"⚡ 开始并行获取数据...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有数据获取任务
        futures = {}
        
        # 市场情绪（无论个股还是板块都需要）
        futures['market_sentiment'] = executor.submit(_fetch_market_sentiment)
        
        if not is_sector:
            # 个股数据获取任务
            futures['financials'] = executor.submit(_fetch_financials, stock_code)
            futures['fund_flow'] = executor.submit(_fetch_fund_flow, stock_code)
            futures['industry_data'] = executor.submit(_fetch_industry_data, stock_code)
            futures['valuation_history'] = executor.submit(_fetch_valuation_history, stock_code)
        
        # 等待所有任务完成
        for future in as_completed(futures.values()):
            try:
                future.result()
            except Exception as e:
                print(f"⚠️ 并行任务失败: {e}")
    
    # 收集结果
    def _safe_result(key, default):
        try:
            return futures[key].result()
        except Exception as e:
            print(f"⚠️ 并行任务 {key} 失败: {e}")
            return default
    
    market_sentiment = _safe_result('market_sentiment', {})
    
    if not is_sector:
        financials = _safe_result('financials', {})
        fund_flow = _safe_result('fund_flow', {})
        industry_data = _safe_result('industry_data', {})
        valuation_history = _safe_result('valuation_history', {})
    
    elapsed_time = time.time() - start_time
    print(f"✅ 并行数据获取完成，耗时: {elapsed_time:.2f}秒")
    
    if isinstance(df, pd.DataFrame) and not df.empty and len(df) >= 10:
        try:
            # 确保数据按日期升序
            df = df.sort_values('dt')
            
            # 1. 均线系统 (MA)
            df["MA5"] = df["close"].rolling(window=5).mean()
            df["MA10"] = df["close"].rolling(window=10).mean()
            df["MA20"] = df["close"].rolling(window=20).mean()
            df["MA60"] = df["close"].rolling(window=60).mean()
            
            # 2. 指数平滑异同平均线 (MACD)
            exp1 = df["close"].ewm(span=12, adjust=False).mean()
            exp2 = df["close"].ewm(span=26, adjust=False).mean()
            df["MACD"] = exp1 - exp2
            df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
            df["Hist"] = df["MACD"] - df["Signal"]
            
            # 3. 相对强弱指标 (RSI)
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            # 4. 布林带 (BOLL)
            df["BOLL_MID"] = df["close"].rolling(window=20).mean()
            df["BOLL_STD"] = df["close"].rolling(window=20).std()
            df["BOLL_UPPER"] = df["BOLL_MID"] + 2 * df["BOLL_STD"]
            df["BOLL_LOWER"] = df["BOLL_MID"] - 2 * df["BOLL_STD"]
            
            # 5. 随机指标 (KDJ)
            low_list = df["low"].rolling(9, min_periods=9).min()
            high_list = df["high"].rolling(9, min_periods=9).max()
            rsv = (df["close"] - low_list) / (high_list - low_list) * 100
            df["KDJ_K"] = rsv.ewm(com=2).mean()
            df["KDJ_D"] = df["KDJ_K"].ewm(com=2).mean()
            df["KDJ_J"] = 3 * df["KDJ_K"] - 2 * df["KDJ_D"]
            
            # 6. 成交量分析
            df["VMA5"] = df["volume"].rolling(window=5).mean()
            df["VMA10"] = df["volume"].rolling(window=10).mean()
            
            # 仅对基础列填充 NaN，保留技术指标的 NaN 以避免误导形态识别
            base_cols = ["open", "close", "high", "low", "volume", "adj_close"]
            df[base_cols] = df[base_cols].fillna(0)
            
            vma5_last = df["VMA5"].iloc[-1] if not pd.isna(df["VMA5"].iloc[-1]) else 0
            volume_ratio = df["volume"].iloc[-1] / vma5_last if vma5_last != 0 else 1
            
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
            
            if last_row["close"] > last_row["BOLL_UPPER"]: patterns.append("布林带上轨压力")
            elif last_row["close"] < last_row["BOLL_LOWER"]: patterns.append("布林带下轨支撑")

            # --- 经典 K 线形态 (基于最近两根蜡烛) ---
            body = last_row["close"] - last_row["open"]
            abs_body = abs(body)
            upper_shadow = last_row["high"] - max(last_row["open"], last_row["close"])
            lower_shadow = min(last_row["open"], last_row["close"]) - last_row["low"]
            
            prev_body = prev_row["close"] - prev_row["open"]
            
            # 1. 锤子线/倒锤子线 (底部信号)
            if lower_shadow > 2 * abs_body and upper_shadow < 0.1 * abs_body:
                patterns.append("锤子线 (潜在底部反转)")
            if upper_shadow > 2 * abs_body and lower_shadow < 0.1 * abs_body:
                patterns.append("倒锤子线 (潜在底部信号)")
                
            # 2. 十字星
            if abs_body < (last_row["high"] - last_row["low"]) * 0.1:
                patterns.append("十字星 (多空博弈激烈/变盘信号)")
                
            # 3. 看涨/看跌吞没
            if last_row["close"] > last_row["open"] and prev_row["close"] < prev_row["open"]:
                if last_row["close"] > prev_row["open"] and last_row["open"] < prev_row["close"]:
                    patterns.append("看涨吞没 (强力反转)")
            if last_row["close"] < last_row["open"] and prev_row["close"] > prev_row["open"]:
                if last_row["close"] < prev_row["open"] and last_row["open"] > prev_row["close"]:
                    patterns.append("看跌吞没 (强力压制)")

            # 4. 向上/向下跳空
            if last_row["low"] > prev_row["high"]:
                patterns.append("向上跳空缺口 (动能强劲)")
            if last_row["high"] < prev_row["low"]:
                patterns.append("向下跳空缺口 (恐慌抛售)")

            # --- 5. 量价协同分析 (专业进阶) ---
            # 计算 OBV (能量潮指标)
            df["OBV"] = (df["volume"] * ((df["close"] > df["close"].shift(1)).astype(int) * 2 - 1)).fillna(0).cumsum()

            avg_vol = df["volume"].tail(5).mean()
            price_change = (last_row["close"] - prev_row["close"]) / prev_row["close"]
            vol_change = (last_row["volume"] - prev_row["volume"]) / prev_row["volume"]

            if price_change > 0.02 and last_row["volume"] > avg_vol * 1.5:
                patterns.append("放量上涨 (趋势确认)")
            elif price_change > 0.02 and last_row["volume"] < avg_vol * 0.7:
                patterns.append("缩量上涨 (动能不足/背离)")
            elif price_change < -0.02 and last_row["volume"] > avg_vol * 1.5:
                patterns.append("放量下跌 (恐慌盘杀出)")
            elif price_change < -0.02 and last_row["volume"] < avg_vol * 0.7:
                patterns.append("无量阴跌 (阴跌无底/警惕)")

            # OBV 趋势判断
            if df["OBV"].iloc[-1] > df["OBV"].iloc[-5]:
                patterns.append("OBV 能量潮上升 (资金持续流入)")
            
            # 8. 数据清洗 (防止 NaN/Inf 传递给大模型导致幻觉)
            def clean_value(val, name="指标"):
                if pd.isna(val) or val == float('inf') or val == float('-inf'):
                    return f"数据不足无法计算{name}"
                return round(float(val), 3)

            latest_price = last_row["close"]
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
                "fundamental": {
                    "pe": clean_value(last_row.get("pe"), "PE(静)"),
                    "roe": clean_value(last_row.get("roe"), "ROE(%)"),
                    "peg": clean_value(last_row.get("peg"), "PEG"),
                    "net_profit_growth": clean_value(last_row.get("net_profit_growth"), "净利增长(%)")
                },
                "volume_ratio": clean_value(volume_ratio, "量比"),
                "patterns": patterns
            }
            
            # 9. 运行量化回测 (核心升级：不再只选一个最好，而是给出候选集)
            print(f"--- 🔄 正在运行量化策略候选回测 --- ")
            backtest_results = []
            engine = VectorizedEngine(
                initial_cash=float(config.get("backtest_initial_cash", 100000.0)),
                commission=float(config.get("backtest_commission", 0.0003)),
                slippage=float(config.get("backtest_slippage", 0.001)),
            )
            persistence = BacktestPersistence()

            dt_min = df["dt"].min() if "dt" in df.columns and not df.empty else None
            dt_max = df["dt"].max() if "dt" in df.columns and not df.empty else None
            data_info = {
                "symbol": stock_code,
                "rows": int(len(df)),
                "dt_min": dt_min.isoformat() if hasattr(dt_min, "isoformat") else None,
                "dt_max": dt_max.isoformat() if hasattr(dt_max, "isoformat") else None,
                "data_hash": _hash_ohlcv(df),
            }
            engine_info = {
                "initial_cash": engine.initial_cash,
                "commission": engine.commission,
                "slippage": engine.slippage,
            }

            max_runs = int(config.get("backtest_max_runs", 20))  # 优化：从 40 减少到 20，提升性能
            runs = 0
            skipped_by_missing = []
            
            for name, strategy_cls in STRATEGY_REGISTRY.items():
                required_cols = getattr(strategy_cls, "required_columns", []) or []
                missing = [c for c in required_cols if c not in df.columns]
                if missing:
                    skipped_by_missing.append({"name": name, "missing": missing})
                    continue

                grids = getattr(strategy_cls, "param_grid", None) or [None]
                for params in grids:
                    if runs >= max_runs:
                        break
                    try:
                        strategy = strategy_cls(params=params)
                        run_results = engine.run(strategy, df)
                        metrics = PerformanceAnalytics.calculate_metrics(
                            run_results, initial_cash=engine.initial_cash
                        )
                        strategy_params = strategy.params.model_dump()

                        # 保存回测记录
                        persistence.save_result(
                            name,
                            strategy_params,
                            metrics,
                            data_info=data_info,
                            engine_info=engine_info,
                        )

                        # Web 模式（state.config 携带 report_id）下同步入库 Django
                        # BacktestResult，供 /api/backtests/ 查询；CLI 无该键则跳过。
                        report_id = config.get("report_id")
                        if report_id:
                            try:
                                from backend.backtests.services import record_backtest
                                record_backtest(
                                    report_id, name, strategy_params, metrics,
                                    data_info=data_info, engine_info=engine_info,
                                )
                            except Exception as db_err:
                                print(f"⚠️ 回测记录入库失败 ({name}): {db_err}")

                        label = name
                        formatted = _format_params(strategy_params)
                        if formatted:
                            label = f"{name} ({formatted})"

                        backtest_results.append({
                            "name": name,
                            "label": label,
                            "params": strategy_params,
                            "metrics": metrics,
                            "summary": PerformanceAnalytics.get_summary_report(metrics),
                        })
                        runs += 1
                    except Exception as e:
                        if isinstance(e, KeyError):
                            missing_key = str(e).strip("'\"")
                            skipped_by_missing.append({"name": name, "missing": [missing_key]})
                            continue
                        print(f"策略 {name} 回测失败: {e}")
                        runs += 1

            # 按夏普比率排序
            backtest_results = sorted(backtest_results, key=lambda x: x["metrics"].get("sharpe", 0), reverse=True)
            if skipped_by_missing:
                unique_missing = sorted({m for item in skipped_by_missing for m in item.get("missing", [])})
                preview = ", ".join(unique_missing[:8])
                suffix = "..." if len(unique_missing) > 8 else ""
                print(f"ℹ️ 已跳过 {len(skipped_by_missing)} 个策略，缺少字段: {preview}{suffix}")
            
            # 10. 组装结果
            quant_data = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "technical_indicators": tech_indicators,
                "financials": financials,
                "fund_flow": fund_flow,
                "industry_comparison": industry_data,
                "valuation_history": valuation_history,
                "market_sentiment": market_sentiment,
                "backtest_candidates": backtest_results # 传递候选策略集
            }
            
            return {
                "quant_data": quant_data,
                "technical_indicators": tech_indicators,
                "messages": [f"已完成 {stock_name} 的量化数据获取与多策略回测分析。"],
                "consecutive_failures": state.get("consecutive_failures", 0)
            }
            
        except Exception as e:
            import traceback
            print(f"量化分析过程出错: {e}")
            print(traceback.format_exc())
            return {"error": f"量化分析失败: {str(e)}", "consecutive_failures": state.get("consecutive_failures", 0)}
    else:
        return {"error": "获取到的数据不足以进行量化分析", "consecutive_failures": state.get("consecutive_failures", 0)}
