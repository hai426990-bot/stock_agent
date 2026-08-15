"""tools/stock_data.py 多数据源回退与缓存策略的单元测试 (无网络, 全部 mock)。

覆盖:
- 主源 (东方财富) 正常时走主源
- 主源超时/失败时回退备用源 (新浪/同花顺/10jqka)
- stale-if-error: 上游不可用时回退过期缓存
- 失败/空结果不写入缓存
"""
import itertools
import os

import pandas as pd
import pytest

import tools.stock_data as sd


_tmp_counter = itertools.count()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """隔离缓存 (指向临时文件), 避免污染项目真实 .akshare_cache.json。

    说明: 使用项目内临时目录而非 pytest 的 tmp_path, 保证在受限的
    沙箱环境下也可运行。
    """
    tmp_dir = os.path.join(os.path.dirname(__file__), "..", "..", ".pytest_tmp_cache")
    os.makedirs(tmp_dir, exist_ok=True)
    cache_file = os.path.join(tmp_dir, f"ttl_cache_{next(_tmp_counter)}.json")
    monkeypatch.setattr(sd, "_cache_instance", sd.TTLCache(cache_file))
    # retry 装饰器的指数退避等待在测试中直接跳过
    monkeypatch.setattr("tools.retry.time.sleep", lambda s: None)
    yield
    for path in (cache_file, tmp_dir):
        try:
            if os.path.isdir(path):
                os.rmdir(path)
            elif os.path.exists(path):
                os.remove(path)
        except OSError:
            pass  # 目录非空或已被清理时忽略


# ----------------------------------------------------------------------
# 构造 mock 数据
# ----------------------------------------------------------------------

def _em_hist_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "日期": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
        "开盘": [10.0] * n,
        "收盘": [11.0] * n,
        "最高": [12.0] * n,
        "最低": [9.0] * n,
        "成交量": [1000] * n,
    })


def _sina_hist_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
        "open": [10.0] * n,
        "high": [12.0] * n,
        "low": [9.0] * n,
        "close": [11.0] * n,
        "volume": [1000] * n,
        "turnover": [0.01] * n,
    })


def _boom(*args, **kwargs):
    raise RuntimeError("upstream down")


# ----------------------------------------------------------------------
# 历史 K 线: 东方财富 -> 新浪
# ----------------------------------------------------------------------

def test_hist_em_primary(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_hist", lambda **kw: _em_hist_df())
    df = sd.get_stock_hist_data("600519")
    assert not df.empty
    assert "日期" in df.columns and "开盘" in df.columns and "成交量" in df.columns


def test_hist_sina_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_hist", _boom)
    monkeypatch.setattr(sd.ak, "stock_zh_a_daily", lambda **kw: _sina_hist_df())
    df = sd.get_stock_hist_data("600519")
    assert not df.empty
    assert list(df.columns) == ["日期", "开盘", "最高", "最低", "收盘", "成交量", "换手率"]


def test_hist_both_sources_down_returns_empty(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_hist", _boom)
    monkeypatch.setattr(sd.ak, "stock_zh_a_daily", _boom)
    df = sd.get_stock_hist_data("600519")
    assert df is not None and df.empty


# ----------------------------------------------------------------------
# 缓存策略: stale-if-error / 空结果不缓存
# ----------------------------------------------------------------------

def test_stale_if_error_serves_expired_cache(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_hist", lambda **kw: _em_hist_df(3))
    first = sd.get_stock_hist_data("600519")
    assert not first.empty

    monkeypatch.setattr(sd.ak, "stock_zh_a_hist", _boom)
    monkeypatch.setattr(sd.ak, "stock_zh_a_daily", _boom)
    second = sd.get_stock_hist_data("600519")
    # 上游不可用时回退过期缓存, 而不是返回空
    assert not second.empty
    assert len(second) == len(first)


def test_empty_result_not_cached(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_hist", _boom)
    monkeypatch.setattr(sd.ak, "stock_zh_a_daily", _boom)
    out = sd.get_stock_hist_data("600519")
    assert out is not None and out.empty

    cached, _ = sd._cache_instance.get("get_stock_hist_data", ("600519",), {})
    assert cached is None


# ----------------------------------------------------------------------
# 全市场快照: 东方财富 -> 新浪
# ----------------------------------------------------------------------

def test_spot_snapshot_sina_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_spot_em", _boom)
    sina = pd.DataFrame({
        "代码": ["600519", "000001"],
        "名称": ["贵州茅台", "平安银行"],
        "最新价": [1700.0, 10.5],
        "涨跌幅": [1.5, -0.3],
    })
    monkeypatch.setattr(sd.ak, "stock_zh_a_spot", lambda: sina)
    df = sd._get_spot_snapshot()
    assert not df.empty
    assert df.iloc[0]["代码"] == "600519"


def test_search_stock_code_uses_snapshot(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_a_spot_em", _boom)
    sina = pd.DataFrame({
        "代码": ["600519"],
        "名称": ["贵州茅台"],
        "最新价": [1700.0],
        "涨跌幅": [1.5],
    })
    monkeypatch.setattr(sd.ak, "stock_zh_a_spot", lambda: sina)
    code, name = sd.search_stock_code("茅台")
    assert code == "600519"
    assert name == "贵州茅台"


# ----------------------------------------------------------------------
# 指数: 新浪 -> 东方财富
# ----------------------------------------------------------------------

def test_market_indices_em_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_zh_index_spot_sina", _boom)
    em = pd.DataFrame({
        "名称": ["上证指数", "深证成指", "创业板指", "科创50", "上证50"],
        "最新价": [3000.0, 9000.0, 2000.0, 1000.0, 2500.0],
        "涨跌额": [10.0, 20.0, 30.0, 40.0, 50.0],
        "涨跌幅": [0.33, 0.22, 1.52, 4.1, 2.0],
    })
    monkeypatch.setattr(sd.ak, "stock_zh_index_spot_em", lambda **kw: em)
    results = sd.get_market_indices()
    assert [r["name"] for r in results] == ["上证指数", "深证成指", "创业板指", "科创50"]
    assert results[0]["price"] == 3000.0


# ----------------------------------------------------------------------
# 新闻: 东方财富 -> 同花顺
# ----------------------------------------------------------------------

def test_news_10jqka_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_news_em", _boom)
    items = [
        {"title": "茅台发布公告", "date": "2024-01-01", "time": "10:00",
         "content": "内容A", "url": "http://a", "stocks": ["贵州茅台(600519)"]},
        {"title": "无关新闻", "date": "2024-01-01", "time": "11:00",
         "content": "内容B", "url": "http://b", "stocks": ["其他(000001)"]},
    ]
    monkeypatch.setattr("tools.news_fetcher.get_10jqka_news", lambda **kw: items)
    news = sd.get_stock_news("600519", with_sector=False)
    assert len(news) == 1
    assert "茅台" in news[0]["新闻标题"]
    assert news[0]["文章链接"] == "http://a"


# ----------------------------------------------------------------------
# 财务/研报/资金流回退
# ----------------------------------------------------------------------

def test_financial_em_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_financial_abstract_ths", _boom)
    em = pd.DataFrame({
        "选项": ["常用"] * 2,
        "指标": ["净利润", "营业总收入"],
        "20240331": [100.0, 200.0],
        "20231231": [90.0, 180.0],
    })
    monkeypatch.setattr(sd.ak, "stock_financial_abstract", lambda **kw: em)
    result = sd.get_stock_financial_indicator("600519")
    assert result.get("净利润") == 100.0
    assert result.get("数据来源") == "东方财富"


def test_profit_forecast_em_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_profit_forecast_ths", _boom)
    em = pd.DataFrame({
        "序号": [1, 2],
        "名称": ["贵州茅台", "贵州茅台"],
        "研报日期": ["2024-01-01", "2024-02-01"],
        "机构名称": ["机构A", "机构B"],
    })
    monkeypatch.setattr(sd.ak, "stock_profit_forecast_em", lambda **kw: em)
    result = sd.get_stock_report("600519")
    assert len(result) == 2
    assert result[0]["机构名称"] == "机构A"


def test_fund_flow_individual_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_individual_fund_flow_rank", _boom)
    hist = pd.DataFrame({
        "日期": ["2024-01-01"],
        "收盘价": [1700.0],
        "涨跌幅": [1.5],
        "主力净流入-净额": [12345.0],
        "主力净流入-净占比": [1.2],
    })
    monkeypatch.setattr(sd.ak, "stock_individual_fund_flow", lambda **kw: hist)
    result = sd.get_stock_fund_flow("600519")
    assert result["数据状态"] == "正常"
    assert result["今日主力净流入-净额"] == 12345.0
    assert result["数据来源"] == "东方财富(个股资金流)"


# ----------------------------------------------------------------------
# 板块: 东方财富 -> 同花顺
# ----------------------------------------------------------------------

def test_search_board_info_ths_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_board_industry_name_em", _boom)
    monkeypatch.setattr(sd.ak, "stock_board_concept_name_em", _boom)
    ths_industry = pd.DataFrame({"name": ["酿酒"], "code": ["881001"]})
    ths_concept = pd.DataFrame({"name": ["白酒概念"], "code": ["308001"]})
    monkeypatch.setattr(sd.ak, "stock_board_industry_name_ths", lambda: ths_industry)
    monkeypatch.setattr(sd.ak, "stock_board_concept_name_ths", lambda: ths_concept)

    industry = sd.search_board_info("酿酒")
    assert industry == {"name": "酿酒", "code": "881001", "type": "industry"}

    concept = sd.search_board_info("白酒")
    assert concept == {"name": "白酒概念", "code": "308001", "type": "concept"}


def test_hot_sectors_ths_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_board_industry_name_em", _boom)
    # 同花顺名称列表只有 name/code, 无行情字段 -> 应继续回退到板块摘要
    monkeypatch.setattr(sd.ak, "stock_board_industry_name_ths",
                        lambda: pd.DataFrame({"name": ["板块A", "板块B"], "code": ["1", "2"]}))
    ths_summary = pd.DataFrame({
        "板块": ["板块A", "板块B"],
        "涨跌幅": [5.0, 2.0],
        "领涨股": ["股A", "股B"],
        "均价": [1000.0, 2000.0],
    })
    monkeypatch.setattr(sd.ak, "stock_board_industry_summary_ths", lambda: ths_summary)
    result = sd.get_market_hot_sectors(limit=5)
    assert result[0]["板块名称"] == "板块A"
    assert result[0]["领涨股票"] == "股A"
    assert result[0]["最新价"] == 1000.0


def test_board_hist_ths_fallback(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_board_industry_hist_em", _boom)
    # 同花顺行业指数使用自己的命名, 先经过名称翻译 (这里精确匹配)
    monkeypatch.setattr(sd.ak, "stock_board_industry_name_ths",
                        lambda: pd.DataFrame({"name": ["半导体"], "code": ["881121"]}))
    ths = pd.DataFrame({
        "日期": ["2024-01-01", "2024-01-02"],
        "开盘价": [100.0, 101.0],
        "最高价": [102.0, 103.0],
        "最低价": [99.0, 100.0],
        "收盘价": [101.0, 102.0],
    })
    monkeypatch.setattr(sd.ak, "stock_board_industry_index_ths", lambda **kw: ths)
    df = sd.get_board_hist_data("半导体", board_type="industry", days=150)
    assert not df.empty
    assert "开盘" in df.columns and "收盘" in df.columns


# ----------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------

def test_ths_industry_name_translation(monkeypatch):
    monkeypatch.setattr(sd.ak, "stock_board_industry_name_ths",
                        lambda: pd.DataFrame({"name": ["白酒", "半导体"], "code": ["881273", "881121"]}))
    # 精确匹配
    assert sd._ths_industry_name("半导体") == "半导体"
    # 同义词映射 (东方财富 "酿酒行业" -> 同花顺 "白酒")
    assert sd._ths_industry_name("酿酒行业") == "白酒"
    # 无法匹配
    assert sd._ths_industry_name("不存在的板块") is None


def test_public_functions_are_cached():
    """防回归: 所有公开数据函数都必须带 ttl_cache 装饰器 (含 get_last_updated)。"""
    names = [
        "get_stock_hist_data", "get_stock_financial_indicator", "get_stock_news",
        "get_stock_report", "get_stock_fund_flow", "search_board_info",
        "get_board_hist_data", "get_board_cons", "get_board_news",
        "get_stock_industry_comparison", "get_stock_valuation_history",
        "get_market_sentiment", "get_market_indices", "get_market_hot_sectors",
        "search_stock_code",
    ]
    for name in names:
        assert hasattr(getattr(sd, name), "get_last_updated"), f"{name} 缺少 ttl_cache 装饰器"


def test_sina_symbol():
    assert sd._sina_symbol("600519") == "sh600519"
    assert sd._sina_symbol("000001") == "sz000001"
    assert sd._sina_symbol("430047") == "bj430047"
    assert sd._sina_symbol("sh600000") == "sh600000"
