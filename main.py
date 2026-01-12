from graph import create_alpha_flow_graph
from tools.stock_data import search_stock_code, get_cache_status
from dotenv import load_dotenv
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# 设置控制台编码为 UTF-8，防止 Windows 下 emoji 导致崩溃
def setup_utf8_encoding():
    """
    在 Windows 系统上设置 UTF-8 编码，支持 emoji 字符
    """
    if sys.platform == 'win32':
        try:
            # 尝试使用 reconfigure 方法 (Python 3.7+)
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            else:
                # Python < 3.7 的兼容处理
                import io
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception as e:
            # 如果设置失败，继续运行，但可能会遇到编码问题
            pass

setup_utf8_encoding()

# 加载环境变量，优先使用 .env 配置文件 (override=True)
load_dotenv(override=True)

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
            print("📦 模型探测缓存已过期")
            return None
        
        print(f"📦 使用模型探测缓存: {cache_data.get('model_name', 'unknown')}")
        return cache_data.get("model_name")
    except Exception as e:
        print(f"⚠️ 加载模型缓存失败: {e}")
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
        print(f"💾 模型探测结果已缓存: {model_name}")
    except Exception as e:
        print(f"⚠️ 保存模型缓存失败: {e}")

def detect_available_model(api_key: str, api_base: str, force_redetect: bool = False):
    """
    自动探测可用的模型
    返回第一个可用的模型名称，如果都不可用则返回 None
    
    Args:
        api_key: API Key
        api_base: API Base URL
        force_redetect: 是否强制重新探测（忽略缓存）
    """
    # 如果不强制重新探测，先尝试从缓存加载
    if not force_redetect:
        cached_model = load_model_cache()
        if cached_model:
            return cached_model
    
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
    
    print(f"🔍 开始探测可用模型，候选列表: {', '.join(supported_models)}")
    
    for model_name in supported_models:
        try:
            print(f"  尝试模型: {model_name}...")
            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=5,
                top_p=0.95,
                timeout=10
            )
            llm.invoke("hi")
            print(f"  ✅ 模型 {model_name} 可用")
            
            # 保存到缓存
            save_model_cache(model_name)
            
            return model_name
        except Exception as e:
            print(f"  ❌ 模型 {model_name} 不可用: {str(e)[:50]}")
            continue
    
    print("❌ 所有候选模型均不可用")
    return None

def run_alpha_flow(input_str: str):
    """
    运行 AlphaFlow 投资决策系统
    input_str: 可以是股票代码 (如 600519) 或股票名称 (如 贵州茅台)
    """
    # 检查并获取 API Key
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    # 优先获取用户在环境变量中显式指定的模型名称
    model_name = os.getenv("MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME") or os.getenv("OPENAI_MODEL")

    if not api_key or api_key == "your_openai_api_key":
        print("⚠️ 错误: 请在 .env 文件中配置有效的 OPENAI_API_KEY")
        return

    # 模型可用性预检
    print(f"\n🧪 模型可用性预检...")
    
    # 如果环境变量已经指定了模型，先尝试使用该模型
    available_model = None
    if model_name:
        print(f"  尝试使用环境变量指定的模型: {model_name}...")
        from langchain_openai import ChatOpenAI
        try:
            llm_kwargs = {
                "model": model_name,
                "api_key": api_key,
                "base_url": api_base,
                "max_tokens": 5,
                "top_p": 0.95,
                "timeout": 10
            }
            # 默认开启深度思考探测 (如果模型支持)
            llm_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            
            llm = ChatOpenAI(**llm_kwargs)
            llm.invoke("hi")
            available_model = model_name
            print(f"  ✅ 指定模型 {model_name} 可用")
        except Exception as e:
            print(f"  ❌ 指定模型 {model_name} 不可用，将尝试自动探测其他可用模型...")
    
    # 如果指定模型不可用或未指定，则进行自动探测
    if not available_model:
        available_model = detect_available_model(api_key, api_base)
    
    if not available_model:
        print("\n❌ 错误: 无法找到可用的模型")
        print("💡 解决方案:")
        print("   1. 检查 API Key 是否正确")
        print("   2. 检查 API Base URL 是否正确")
        print("   3. 在 .env 文件中配置 SUPPORTED_MODELS，列出您的 API 服务商支持的模型")
        print("   4. 确保网络连接正常")
        print("   5. 如果使用代理，请检查代理设置")
        return
    
    # 使用探测到的可用模型
    model_name = available_model
    print(f"✅ 使用模型: {model_name}\n")

    # 识别输入是代码还是名称
    stock_code = ""
    stock_name = ""
    
    if input_str.isdigit() and len(input_str) == 6:
        stock_code = input_str
        stock_name = input_str # 稍后可以在节点中进一步完善
    else:
        print(f"🔍 正在搜索股票代码: {input_str}...")
        stock_code, stock_name = search_stock_code(input_str)
        if not stock_code:
            print(f"❌ 未找到匹配的股票: {input_str}")
            return
        print(f"✅ 已找到: {stock_name} ({stock_code})")

    # 初始化状态
    backtest_lookback_days = int(os.getenv("BACKTEST_LOOKBACK_DAYS", "365"))
    backtest_sector_days = int(os.getenv("BACKTEST_SECTOR_DAYS", "252"))
    backtest_initial_cash = float(os.getenv("BACKTEST_INITIAL_CASH", "100000"))
    backtest_commission = float(os.getenv("BACKTEST_COMMISSION", "0.0003"))
    backtest_slippage = float(os.getenv("BACKTEST_SLIPPAGE", "0.001"))

    initial_state = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "news_items": [],
        "news_analysis": "",
        "sentiment_score": 0.0,
        "quant_data": {},
        "technical_indicators": {},
        "backtest_result": {},
        "strategy_report": "",
        "risk_assessment": "",
        "messages": [],
        "revision_needed": False,
        "human_approval": False,
        "count": 0,
        "is_sector": False,
        "error": "",
        "config": {
            "api_key": api_key,
            "api_base": api_base,
            "model_name": model_name,
            "temperature": 0.3,
            "max_tokens": 8196,
            "thinking_mode": True,
            "backtest_lookback_days": backtest_lookback_days,
            "backtest_sector_days": backtest_sector_days,
            "backtest_initial_cash": backtest_initial_cash,
            "backtest_commission": backtest_commission,
            "backtest_slippage": backtest_slippage,
        }
    }
    
    # 创建并运行图
    app = create_alpha_flow_graph()
    
    print(f"\n🚀 AlphaFlow 启动: 正在分析股票 {stock_code} ({stock_name})...\n")
    
    # 运行
    try:
        # 使用 stream 模式以便在节点出错时及时发现
        final_state = initial_state
        for output in app.stream(initial_state):
            for node_name, state_update in output.items():
                final_state.update(state_update)
                # 检查是否有错误发生
                if final_state.get("error"):
                    print(f"\n🛑 流程因节点错误中止: {final_state['error']}")
                    print("💡 常见错误解决方案:")
                    print("   - 模型不支持: 请在 .env 文件中配置 SUPPORTED_MODELS")
                    print("   - API Key 无效: 请检查 OPENAI_API_KEY 是否正确")
                    print("   - 网络连接问题: 请检查网络连接和代理设置")
                    print("   - 数据源问题: AkShare 数据源可能暂时不可用，请稍后重试")
                    return
                # 检查是否有中断信号
                if final_state.get("interrupted"):
                    print(f"\n⏸️ 流程被用户中断")
                    return
        
        # 输出最终结果
        print("\n" + "="*50)
        print("📦 数据缓存状态")
        print("="*50)
        
        cache_status = get_cache_status(stock_code)
        
        if cache_status and cache_status.get("data_sources"):
            print(f"缓存文件: {cache_status['cache_file']}")
            print(f"总缓存条目: {cache_status['cache_size']}")
            print("\n各数据源最后更新时间:")
            
            data_sources = cache_status["data_sources"]
            has_cached_data = False
            for source_name, source_info in data_sources.items():
                last_updated = source_info.get("last_updated")
                if last_updated:
                    try:
                        dt = datetime.fromisoformat(last_updated)
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  - {source_name}: {time_str}")
                        has_cached_data = True
                    except:
                        print(f"  - {source_name}: {last_updated}")
                        has_cached_data = True
                else:
                    print(f"  - {source_name}: 未缓存")
            
            if not has_cached_data:
                print("  (暂无缓存数据)")
        else:
            print("暂无缓存数据")
        
        quant_data = final_state.get("quant_data", {})
        candidates = quant_data.get("backtest_candidates", [])
        if candidates:
            print("\n" + "="*50)
            print("📈 回测与策略候选集")
            print("="*50)
            for i, cand in enumerate(candidates[:3]): # 只打印前3个
                print(f"[{i+1}] 策略: {cand.get('name')}")
                metrics = cand.get('metrics', {})
                print(f"    Sharpe: {metrics.get('sharpe', 0):.2f} | CAGR: {metrics.get('cagr', 0)*100:.2f}% | MDD: {metrics.get('max_drawdown', 0)*100:.2f}%")
            if len(candidates) > 3:
                print(f"    ... 还有 {len(candidates)-3} 个候选策略已保存到 persistence 层")
        else:
            print("\n" + "="*50)
            print("📈 回测与策略筛选")
            print("="*50)
            print("暂无可用的候选策略结果")

        print("\n" + "="*50)
        print("📋 最终投资建议报告")
        print("="*50)
        print(final_state.get("strategy_report", "未生成报告"))
        print("\n" + "="*50)
        print("🛡️ 风控审核意见")
        print("="*50)
        risk_assessment = final_state.get("risk_assessment", {})
        
        # 处理结构化的风控结果
        if isinstance(risk_assessment, dict):
            decision = risk_assessment.get("decision", "未知")
            reason = risk_assessment.get("reason", "未提供详细理由")
            review_count = risk_assessment.get("review_count", 0)
            review_date = risk_assessment.get("review_date", "")
            
            print(f"【决策: {decision}】")
            print(f"【审核次数: {review_count}】")
            if review_date:
                print(f"【审核日期: {review_date}】")
            print(f"\n{reason}")
            
            # 检查是否为强制通过
            if decision == "强制通过":
                print("\n⚠️ **重要提示**: 该报告已达到最大修订次数，系统强制通过。")
                print("⚠️ **风险提示**: 请仔细阅读风控官的末次风险提示，建议人工复核后再做投资决策。")
        else:
            # 兼容旧格式（字符串）
            print(risk_assessment)
            if "强制通过" in str(risk_assessment):
                print("\n⚠️ **重要提示**: 该报告已达到最大修订次数，系统强制通过。")
                print("⚠️ **风险提示**: 请仔细阅读风控官的末次风险提示，建议人工复核后再做投资决策。")
        print("="*50)
        print("✨ 分析任务完成")
    except Exception as e:
        print(f"💥 系统运行出错: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='AlphaFlow 股票分析系统')
    parser.add_argument('--stock', type=str, help='股票代码或名称 (例如: 600519 或 贵州茅台)')
    
    args = parser.parse_args()
    
    # 可以通过命令行输入或直接修改此处
    if args.stock:
        run_alpha_flow(args.stock)
    else:
        user_input = input("请输入股票名称或代码 (例如: 贵州茅台 或 600519): ").strip()
        if user_input:
            run_alpha_flow(user_input)
        else:
            run_alpha_flow("600519") # 默认测试茅台
