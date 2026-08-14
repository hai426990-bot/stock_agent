"""
AlphaFlow 命令行界面 (CLI) 主程序

本模块提供 AlphaFlow 系统的命令行界面,支持通过命令行进行股票分析和回测。

主要功能:
    - 股票代码/名称搜索和识别
    - 自动探测可用的 LLM 模型
    - 多智能体协作分析流程
    - 实时分析进度显示
    - 分析结果展示和报告输出

使用方式:
    python main.py --stock 600519
    python main.py --stock 贵州茅台

依赖:
    - LangGraph: 工作流编排
    - LangChain: LLM 集成
    - AkShare: 股票数据获取
"""

from graph import create_alpha_flow_graph
from tools.stock_data import search_stock_code, get_cache_status
from config import get_config_manager, get_config, set_runtime_config
from logger import get_logger
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

config_manager = get_config_manager()
logger = get_logger(__name__)

# 设置控制台编码为 UTF-8，防止 Windows 下 emoji 导致崩溃
def setup_utf8_encoding():
    """
    在 Windows 系统上设置 UTF-8 编码，支持 emoji 字符显示

    该函数确保在 Windows 系统上正确显示 emoji 和中文字符。
    对于 Python 3.7+ 使用 reconfigure 方法,对于旧版本使用 TextIOWrapper。

    Raises:
        Exception: 如果编码设置失败,会捕获异常并继续运行
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
            logger.warning(f"设置 UTF-8 编码失败: {e}")

setup_utf8_encoding()

# 模型探测缓存文件路径
MODEL_CACHE_FILE = Path(__file__).parent / ".model_cache.json"

def main():
    logger.info("AlphaFlow CLI 启动")
    try:
        args = sys.argv[1:]
        if not args:
            print("请提供股票代码或名称，例如: python main.py --stock 600519")
            return

        stock_name = args[1] if args[0] == "--stock" else args[0]
        run_alpha_flow(stock_name)
    except Exception as e:
        logger.error(f"程序运行出错: {e}")



def save_model_cache(model_name: str):
    """
    保存模型探测结果到缓存文件

    将探测到的可用模型名称保存到缓存文件,包括时间戳信息。

    Args:
        model_name: 可用的模型名称
    """
    try:
        cache_data = {
            "model_name": model_name,
            "cache_time": datetime.now().isoformat()
        }
        with open(MODEL_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        logger.info(f"模型探测结果已缓存: {model_name}")
    except Exception as e:
        logger.error(f"保存模型缓存失败: {e}")


def detect_available_model(api_key: str, api_base: str, force_redetect: bool = False) -> str:
    """
    自动探测可用的模型

    按照配置中的模型列表顺序尝试连接 API,返回第一个可用的模型名称。
    如果所有模型都不可用,返回 None。

    探测逻辑:
        1. 如果不强制重新探测,先尝试从缓存加载
        2. 遍历配置中的模型列表
        3. 对每个模型发送简单测试请求
        4. 返回第一个成功的模型
        5. 将结果保存到缓存

    Args:
        api_key: API 密钥
        api_base: API 基础 URL
        force_redetect: 是否强制重新探测(忽略缓存)

    Returns:
        Optional[str]: 第一个可用的模型名称,如果都不可用则返回 None

    Raises:
        Exception: 如果模型探测过程中发生异常
    """
    # 如果不强制重新探测，先尝试从缓存加载
    if not force_redetect:
        cached_model = load_model_cache()
        if cached_model:
            return cached_model
    
    from langchain_openai import ChatOpenAI
    
    # 从配置获取支持的模型列表
    supported_models = config_manager.get("supported_models", ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "mimo-v2-flash"])
    
    logger.info(f"开始探测可用模型，候选列表: {', '.join(supported_models)}")
    
    for model_name in supported_models:
        try:
            print(f"  尝试模型: {model_name}...")
            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=api_base,
                max_tokens=5,
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

    执行完整的股票分析流程,包括:
    1. 配置验证和模型探测
    2. 股票代码识别
    3. 多智能体协作分析
    4. 结果展示和报告输出

    Args:
        input_str: 股票代码(如 600519)或股票名称(如 贵州茅台)

    Raises:
        Exception: 如果系统运行过程中发生异常

    Example:
        >>> run_alpha_flow("600519")
        >>> run_alpha_flow("贵州茅台")
    """
    # 从配置获取 API Key
    api_key = config_manager.get("api_key", "")
    
    # 从配置获取 API Base URL
    api_base = config_manager.get("api_base", "https://api.openai.com/v1")
    
    # 从配置获取模型名称
    model_name = config_manager.get("model_name", "gpt-4o")

    if not api_key or api_key == "your_openai_api_key":
        logger.error("错误: 请在配置文件中设置有效的 api_key")
        logger.info("解决方案:")
        logger.info("  1. 在 config_user.json 中设置 api_key")
        logger.info("  2. 或在 .env 文件中设置 OPENAI_API_KEY")
        return

    # 模型自动探测和降级
    logger.info("模型可用性预检...")
    available_model = detect_available_model(api_key, api_base)
    
    if not available_model:
        logger.error("错误: 无法找到可用的模型")
        logger.info("解决方案:")
        logger.info("  1. 检查 API Key 是否正确")
        logger.info("  2. 检查 API Base URL 是否正确")
        logger.info("  3. 在 .env 文件中配置 SUPPORTED_MODELS，列出您的 API 服务商支持的模型")
        logger.info("  4. 确保网络连接正常")
        logger.info("  5. 如果使用代理，请检查代理设置")
        return
    
    # 使用探测到的可用模型
    model_name = available_model
    logger.info(f"使用模型: {model_name}")

    # 识别输入是代码还是名称
    stock_code = ""
    stock_name = ""
    
    if input_str.isdigit() and len(input_str) == 6:
        stock_code = input_str
        stock_name = input_str # 稍后可以在节点中进一步完善
    else:
        logger.info(f"正在搜索股票代码: {input_str}...")
        stock_code, stock_name = search_stock_code(input_str)
        if not stock_code:
            logger.error(f"未找到匹配的股票: {input_str}")
            return
        logger.info(f"已找到: {stock_name} ({stock_code})")

    # 初始化状态
    initial_state = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "news_items": [],
        "news_analysis": "",
        "sentiment_score": 0.0,
        "quant_data": {},
        "technical_indicators": {},
        "strategy_report": "",
        "risk_assessment": "",
        "messages": [],
        "revision_needed": False,
        "human_approval": False,
        "count": 0,
        "is_sector": False,
        "error": "",
        "consecutive_failures": 0,
        "config": {
            "api_key": api_key,
            "api_base": api_base,
            "model_name": model_name,
            "temperature": config_manager.get("llm.temperature", 0.5),
            "max_tokens": config_manager.get("llm.max_tokens", 4096),
            "thinking_mode": config_manager.get("llm.thinking_mode", True),
            "backtest_lookback_days": config_manager.get("backtest.days", 365),
            "backtest_initial_cash": config_manager.get("backtest.cash", 100000.0)
        }
    }
    
    # 创建并运行图
    app = create_alpha_flow_graph()
    
    logger.info(f"AlphaFlow 启动: 正在分析股票 {stock_code} ({stock_name})...")
    
    import threading
    import itertools
    import time
    import sys

    # 简单的加载动画
    stop_loading = False
    def loading_spinner(desc="正在分析中"):
        spinner = itertools.cycle(['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'])
        while not stop_loading:
            sys.stdout.write(f"\r{next(spinner)} {desc}...")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write(f"\r✅ {desc} 完成!          \n")
        sys.stdout.flush()

    # 运行
    try:
        # 使用 stream 模式以便在节点出错时及时发现
        final_state = initial_state
        
        # 启动加载动画
        spinner_thread = threading.Thread(target=loading_spinner, args=("多智能体协作中",))
        spinner_thread.daemon = True
        spinner_thread.start()
        
        for output in app.stream(initial_state):
            for node_name, state_update in output.items():
                final_state.update(state_update)
                # 检查是否有错误发生
                if final_state.get("error"):
                    stop_loading = True
                    spinner_thread.join()
                    logger.error(f"流程因节点错误中止: {final_state['error']}")
                    logger.info("常见错误解决方案:")
                    logger.info("  - 模型不支持: 请在 .env 文件中配置 SUPPORTED_MODELS")
                    logger.info("  - API Key 无效: 请检查 OPENAI_API_KEY 是否正确")
                    logger.info("  - 网络连接问题: 请检查网络连接和代理设置")
                    logger.info("  - 数据源问题: AkShare 数据源可能暂时不可用，请稍后重试")
                    return
                # 检查是否有中断信号
                if final_state.get("interrupted"):
                    stop_loading = True
                    spinner_thread.join()
                    logger.info("流程被用户中断")
                    return
        
        stop_loading = True
        spinner_thread.join()

        # 输出最终结果
        logger.info("="*50)
        logger.info("数据缓存状态")
        logger.info("="*50)
        
        cache_status = get_cache_status(stock_code)
        
        if cache_status and cache_status.get("data_sources"):
            logger.info(f"缓存文件: {cache_status['cache_file']}")
            logger.info(f"总缓存条目: {cache_status['cache_size']}")
            logger.info("各数据源最后更新时间:")
            
            data_sources = cache_status["data_sources"]
            has_cached_data = False
            for source_name, source_info in data_sources.items():
                last_updated = source_info.get("last_updated")
                if last_updated:
                    try:
                        dt = datetime.fromisoformat(last_updated)
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"  - {source_name}: {time_str}")
                        has_cached_data = True
                    except:
                        logger.info(f"  - {source_name}: {last_updated}")
                        has_cached_data = True
                else:
                    logger.info(f"  - {source_name}: 未缓存")
            
            if not has_cached_data:
                logger.info("  (暂无缓存数据)")
        else:
            logger.info("暂无缓存数据")
        
        logger.info("="*50)
        logger.info("最终投资建议报告")
        logger.info("="*50)
        print(final_state.get("strategy_report", "未生成报告"))
        logger.info("="*50)
        logger.info("风控审核意见")
        logger.info("="*50)
        risk_assessment = final_state.get("risk_assessment", {})
        
        # 处理结构化的风控结果
        if isinstance(risk_assessment, dict):
            decision = risk_assessment.get("decision", "未知")
            reason = risk_assessment.get("reason", "未提供详细理由")
            review_count = risk_assessment.get("review_count", 0)
            review_date = risk_assessment.get("review_date", "")
            
            logger.info(f"【决策: {decision}】")
            logger.info(f"【审核次数: {review_count}】")
            if review_date:
                logger.info(f"【审核日期: {review_date}】")
            logger.info(f"\n{reason}")
            
            # 检查是否为强制通过
            if decision == "强制通过":
                logger.warning("重要提示: 该报告已达到最大修订次数，系统强制通过。")
                logger.warning("风险提示: 请仔细阅读风控官的末次风险提示，建议人工复核后再做投资决策。")
        else:
            # 兼容旧格式（字符串）
            print(risk_assessment)
            if "强制通过" in str(risk_assessment):
                logger.warning("重要提示: 该报告已达到最大修订次数，系统强制通过。")
                logger.warning("风险提示: 请仔细阅读风控官的末次风险提示，建议人工复核后再做投资决策。")
        logger.info("="*50)
        logger.info("分析任务完成")
    except Exception as e:
        logger.error(f"系统运行出错: {str(e)}")
        raise

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
