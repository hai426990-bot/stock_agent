"""
测试 AkShare 缓存机制
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tools.stock_data import (
    get_stock_hist_data,
    get_stock_financial_indicator,
    get_stock_news,
    get_stock_report,
    get_stock_fund_flow,
    get_stock_industry_comparison,
    get_cache_status,
    clear_akshare_cache
)
from datetime import datetime

def test_cache_mechanism():
    """测试缓存机制"""
    stock_code = "600519"  # 贵州茅台
    
    print("="*60)
    print("🧪 测试 AkShare 缓存机制")
    print("="*60)
    
    # 清理旧缓存
    print("\n📦 清理旧缓存...")
    clear_akshare_cache(ttl_seconds=0)
    
    # 第一次调用 - 应该从 API 获取数据
    print(f"\n📡 第一次调用 - 从 API 获取数据: {stock_code}")
    start_time = datetime.now()
    
    hist_data = get_stock_hist_data(stock_code)
    print(f"  - 股票历史数据: {'✅ 成功' if not hist_data.empty else '❌ 失败'}")
    
    fin_data = get_stock_financial_indicator(stock_code)
    print(f"  - 财务指标: {'✅ 成功' if fin_data else '❌ 失败'}")
    
    news_data = get_stock_news(stock_code)
    print(f"  - 个股新闻: {'✅ 成功' if news_data else '❌ 失败'}")
    
    report_data = get_stock_report(stock_code)
    print(f"  - 盈利预测: {'✅ 成功' if report_data else '❌ 失败'}")
    
    fund_data = get_stock_fund_flow(stock_code)
    print(f"  - 资金流向: {'✅ 成功' if fund_data else '❌ 失败'}")
    
    comp_data = get_stock_industry_comparison(stock_code)
    print(f"  - 行业对比: {'✅ 成功' if comp_data else '❌ 失败'}")
    
    first_call_time = (datetime.now() - start_time).total_seconds()
    print(f"\n⏱️ 第一次调用总耗时: {first_call_time:.2f} 秒")
    
    # 检查缓存状态
    print(f"\n📊 缓存状态:")
    cache_status = get_cache_status(stock_code)
    print(f"  - 缓存文件: {cache_status['cache_file']}")
    print(f"  - 缓存条目数: {cache_status['cache_size']}")
    
    # 第二次调用 - 应该从缓存获取数据
    print(f"\n📦 第二次调用 - 从缓存获取数据: {stock_code}")
    start_time = datetime.now()
    
    hist_data2 = get_stock_hist_data(stock_code)
    print(f"  - 股票历史数据: {'✅ 成功' if not hist_data2.empty else '❌ 失败'}")
    
    fin_data2 = get_stock_financial_indicator(stock_code)
    print(f"  - 财务指标: {'✅ 成功' if fin_data2 else '❌ 失败'}")
    
    news_data2 = get_stock_news(stock_code)
    print(f"  - 个股新闻: {'✅ 成功' if news_data2 else '❌ 失败'}")
    
    report_data2 = get_stock_report(stock_code)
    print(f"  - 盈利预测: {'✅ 成功' if report_data2 else '❌ 失败'}")
    
    fund_data2 = get_stock_fund_flow(stock_code)
    print(f"  - 资金流向: {'✅ 成功' if fund_data2 else '❌ 失败'}")
    
    comp_data2 = get_stock_industry_comparison(stock_code)
    print(f"  - 行业对比: {'✅ 成功' if comp_data2 else '❌ 失败'}")
    
    second_call_time = (datetime.now() - start_time).total_seconds()
    print(f"\n⏱️ 第二次调用总耗时: {second_call_time:.2f} 秒")
    
    # 性能对比
    print(f"\n📈 性能对比:")
    print(f"  - 第一次调用: {first_call_time:.2f} 秒")
    print(f"  - 第二次调用: {second_call_time:.2f} 秒")
    if first_call_time > 0:
        speedup = first_call_time / second_call_time if second_call_time > 0 else float('inf')
        print(f"  - 性能提升: {speedup:.1f}x")
    
    # 显示各数据源的缓存时间
    print(f"\n📋 各数据源缓存时间:")
    data_sources = cache_status.get("data_sources", {})
    for source_name, source_info in data_sources.items():
        last_updated = source_info.get("last_updated")
        if last_updated:
            try:
                dt = datetime.fromisoformat(last_updated)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                print(f"  - {source_name}: {time_str}")
            except:
                print(f"  - {source_name}: {last_updated}")
        else:
            print(f"  - {source_name}: 未缓存")
    
    print("\n" + "="*60)
    print("✅ 缓存机制测试完成")
    print("="*60)

if __name__ == "__main__":
    test_cache_mechanism()