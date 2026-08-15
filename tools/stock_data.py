import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from functools import wraps
import json
import os
import hashlib
from typing import Any, Callable, Optional, Dict, Union
from tools.retry import retry
from tools.http_timeout import install_default_timeout

# 安装全局 HTTP 超时防护: akshare 内部大量 requests/curl_cffi 调用不传
# timeout, 上游 (东方财富/新浪/同花顺) 不可达时请求会无限期挂起。
# 此处注入默认超时后, 所有未显式传 timeout 的请求都会快速失败并触发
# 本模块的多数据源回退与 stale-if-error 缓存。
install_default_timeout()

class TTLCache:
    """
    文件持久化的 TTL 缓存
    """
    # 磁盘写入节流间隔（秒）：避免每次 set 都全量重写缓存文件
    SAVE_INTERVAL = 10.0

    def __init__(self, cache_file: str = ".akshare_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self._dirty = False
        self._last_save = 0.0
    
    def _load_cache(self) -> Dict[str, Any]:
        """加载缓存文件"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 反序列化缓存条目。注意：字符串值保持原样，不能尝试
                # pd.to_datetime 转换——数字型字符串（如 "600519"、价格）
                # 会被误解析成日期，导致缓存数据永久损坏。
                deserialized_cache = {}
                for key, entry in cache_data.items():
                    deserialized_entry = {}
                    for k, v in entry.items():
                        if k == 'data' and isinstance(v, dict) and v.get('type') == 'DataFrame':
                            df_data = v.get('data', [])
                            deserialized_entry[k] = pd.DataFrame(df_data)
                        else:
                            deserialized_entry[k] = v
                    deserialized_cache[key] = deserialized_entry
                
                return deserialized_cache
            except Exception as e:
                print(f"⚠️ 加载缓存文件失败: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """保存缓存到文件（节流：距上次保存不足 SAVE_INTERVAL 秒则跳过）"""
        now = time.time()
        if now - self._last_save < self.SAVE_INTERVAL:
            return
        self._last_save = now
        if not self._dirty:
            return
        self._dirty = False
        try:
            # 处理 DataFrame 序列化
            serializable_cache = {}
            for key, entry in self.cache.items():
                serializable_entry = {}
                for k, v in entry.items():
                    if k == 'data':
                        # 如果是 DataFrame，转换为字典
                        if isinstance(v, pd.DataFrame):
                            # 转换为字典并处理 Timestamp 对象
                            df_dict = v.to_dict(orient='records')
                            # 将 Timestamp 对象转换为字符串
                            serializable_dict = []
                            for row in df_dict:
                                serializable_row = {}
                                for col_key, col_value in row.items():
                                    if isinstance(col_value, pd.Timestamp):
                                        serializable_row[col_key] = col_value.isoformat()
                                    elif hasattr(col_value, '__iter__') and not isinstance(col_value, (str, bytes)):
                                        # 处理包含 Timestamp 的列表或其他可迭代对象
                                        serializable_row[col_key] = str(col_value)
                                    else:
                                        serializable_row[col_key] = col_value
                                serializable_dict.append(serializable_row)
                            
                            serializable_entry[k] = {
                                'type': 'DataFrame',
                                'data': serializable_dict
                            }
                        else:
                            serializable_entry[k] = v
                    else:
                        serializable_entry[k] = v
                serializable_cache[key] = serializable_entry
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存缓存文件失败: {e}")
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_parts = [func_name]
        key_parts.extend([str(arg) for arg in args])
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, func_name: str, args: tuple, kwargs: dict) -> Optional[Any]:
        """获取缓存"""
        key = self._generate_key(func_name, args, kwargs)
        if key in self.cache:
            entry = self.cache[key]
            if 'data' in entry and 'timestamp' in entry:
                return entry['data'], entry['timestamp']
        return None, None
    
    def set(self, func_name: str, args: tuple, kwargs: dict, data: Any):
        """设置缓存（内存立即生效，磁盘节流写入）"""
        key = self._generate_key(func_name, args, kwargs)
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'function': func_name
        }
        self._dirty = True
        self._save_cache()
    
    def clear_expired(self, ttl_seconds: int):
        """清理过期缓存"""
        current_time = datetime.now()
        expired_keys = []
        for key, entry in self.cache.items():
            if 'timestamp' in entry:
                try:
                    cache_time = datetime.fromisoformat(entry['timestamp'])
                    if (current_time - cache_time).total_seconds() > ttl_seconds:
                        expired_keys.append(key)
                except:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self._save_cache()
            print(f"✅ 清理了 {len(expired_keys)} 条过期缓存")
    
    def get_last_updated(self, func_name: str, args: tuple, kwargs: dict) -> Optional[str]:
        """获取最后更新时间"""
        key = self._generate_key(func_name, args, kwargs)
        if key in self.cache and 'timestamp' in self.cache[key]:
            return self.cache[key]['timestamp']
        return None

# 全局缓存实例
_cache_instance = TTLCache()

def _is_empty(result: Any) -> bool:
    """判断数据获取结果是否为空/失败。

    失败结果 (None、空 DataFrame、空容器、带 error/数据状态标记的字典)
    不会被写入缓存, 避免把"上游暂时不可用"当成有效结果缓存整个 TTL。
    """
    if result is None:
        return True
    if isinstance(result, pd.DataFrame):
        return result.empty
    if isinstance(result, dict):
        if not result:
            return True
        if result.get("error"):
            return True
        if result.get("数据状态") in ("异常", "缺失"):
            return True
        return False
    if isinstance(result, (list, str, tuple, set)):
        return len(result) == 0
    return False

def ttl_cache(ttl_seconds: int = 300):
    """
    TTL 缓存装饰器
    ttl_seconds: 缓存过期时间（秒），默认 5 分钟
    """
    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从缓存获取 (命中或已过期都会返回, 过期数据留作 stale 回退)
            cached_data, timestamp = _cache_instance.get(func_name, args, kwargs)
            
            if cached_data is not None:
                try:
                    cache_time = datetime.fromisoformat(timestamp)
                    if (datetime.now() - cache_time).total_seconds() < ttl_seconds:
                        print(f"✅ {func_name} 使用缓存 (更新于: {timestamp})")
                        return cached_data
                except Exception as e:
                    print(f"⚠️ 缓存时间解析失败: {e}")
            
            # 缓存未命中或已过期，调用原函数 (受全局 HTTP 超时防护约束)
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                print(f"⚠️ {func_name} 执行失败: {e}")
                result = None
            
            # 失败或空结果: 不写缓存; 若存在过期缓存则回退 (stale-if-error),
            # 保证上游数据源暂时不可用时仍能返回最近一次成功的数据。
            if _is_empty(result):
                if cached_data is not None:
                    print(f"⚠️ {func_name} 新数据不可用, 回退使用过期缓存 (更新于: {timestamp})")
                    return cached_data
                return result
            
            # 保存到缓存
            _cache_instance.set(func_name, args, kwargs, result)
            
            return result
        
        # 添加获取最后更新时间的方法
        wrapper.get_last_updated = lambda *args, **kwargs: _cache_instance.get_last_updated(func_name, args, kwargs)
        
        return wrapper
    return decorator

def clear_akshare_cache(ttl_seconds: int = 300):
    """清理过期的 AkShare 缓存"""
    _cache_instance.clear_expired(ttl_seconds)

def get_cache_status(stock_code: str = None) -> Dict[str, Any]:
    """
    获取缓存状态信息
    返回各数据源的缓存时间戳和状态
    """
    cache_info = {
        "cache_file": _cache_instance.cache_file,
        "cache_size": len(_cache_instance.cache),
        "data_sources": {}
    }
    
    if stock_code:
        # 获取特定股票的缓存状态
        cache_info["data_sources"]["股票历史数据"] = {
            "last_updated": get_stock_hist_data.get_last_updated(stock_code),
            "function": "get_stock_hist_data"
        }
        cache_info["data_sources"]["财务指标"] = {
            "last_updated": get_stock_financial_indicator.get_last_updated(stock_code),
            "function": "get_stock_financial_indicator"
        }
        cache_info["data_sources"]["个股新闻"] = {
            "last_updated": get_stock_news.get_last_updated(stock_code),
            "function": "get_stock_news"
        }
        cache_info["data_sources"]["盈利预测"] = {
            "last_updated": get_stock_report.get_last_updated(stock_code),
            "function": "get_stock_report"
        }
        cache_info["data_sources"]["资金流向"] = {
            "last_updated": get_stock_fund_flow.get_last_updated(stock_code),
            "function": "get_stock_fund_flow"
        }
        cache_info["data_sources"]["行业对比"] = {
            "last_updated": get_stock_industry_comparison.get_last_updated(stock_code),
            "function": "get_stock_industry_comparison"
        }
    
    return cache_info

# =====================================================================
# 多数据源回退辅助函数
# 每个主数据源 (以东方财富为主) 都配置了独立的回退源 (新浪/同花顺/10jqka),
# 主源超时或不可用时自动切换, 避免单源故障导致整个分析链路挂起。
# =====================================================================

# akshare 接口级超时 (秒): 仅对显式支持 timeout 参数的接口生效;
# 其余接口由 tools.http_timeout 的全局默认超时覆盖。
_AK_TIMEOUT = 15.0


def _sina_symbol(stock_code: str) -> str:
    """把 6 位 A 股代码转换为新浪带市场前缀的代码 (sh/sz/bj)。"""
    if stock_code.startswith(("sh", "sz", "bj")):
        return stock_code
    if stock_code.startswith(("5", "6", "9")):
        return "sh" + stock_code
    if stock_code.startswith(("4", "8")):
        return "bj" + stock_code
    return "sz" + stock_code


def _get_spot_snapshot() -> pd.DataFrame:
    """全市场实时行情快照: 东方财富 -> 新浪 双通道。

    返回的 DataFrame 保证包含 代码/名称/涨跌幅 等核心列 (两源列名一致)。
    """
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            return df
        print("⚠️ 东方财富实时快照为空")
    except Exception as e:
        print(f"⚠️ 东方财富实时快照失败: {e}")
    try:
        df = ak.stock_zh_a_spot()
        if df is not None and not df.empty:
            print(f"✅ 使用新浪数据源获取全市场快照 ({len(df)} 行)")
            return df
        print("⚠️ 新浪实时快照为空")
    except Exception as e:
        print(f"⚠️ 新浪实时快照失败: {e}")
    return pd.DataFrame()


def _fetch_hist_em(stock_code: str) -> pd.DataFrame:
    """个股日线主源: 东方财富 (前复权)。失败时返回空 DataFrame 以触发回退。"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq",
                                timeout=_AK_TIMEOUT)
    except Exception as e:
        print(f"⚠️ 东方财富历史K线失败: {e}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期")
    return df


def _fetch_hist_sina(stock_code: str, days: int = 150) -> pd.DataFrame:
    """个股日线回退源: 新浪 (前复权), 列名对齐东方财富中文 schema。"""
    raw = ak.stock_zh_a_daily(symbol=_sina_symbol(stock_code), adjust="qfq")
    if raw is None or raw.empty:
        return pd.DataFrame()
    rename = {"date": "日期", "open": "开盘", "high": "最高", "low": "最低",
              "close": "收盘", "volume": "成交量", "turnover": "换手率"}
    df = raw.rename(columns={k: v for k, v in rename.items() if k in raw.columns})
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期")
    # 新浪换手率是小数 (如 0.0023), 统一为百分比以对齐东方财富口径
    if "换手率" in df.columns:
        df["换手率"] = df["换手率"] * 100
    print(f"✅ 使用新浪数据源获取 {stock_code} 历史K线 ({len(df)} 行)")
    return df.tail(days)


def _financial_abstract_em(stock_code: str) -> dict:
    """财务摘要回退源: 东方财富 (ak.stock_financial_abstract)。

    返回 {指标: 最新一期数值, 数据来源: ...}, 与同花顺摘要的
    df.iloc[-1].to_dict() 风格一致。
    """
    em = ak.stock_financial_abstract(symbol=stock_code)
    if em is None or em.empty:
        return {}
    period_cols = [c for c in em.columns
                   if isinstance(c, str) and c.isdigit() and len(c) == 8]
    if not period_cols:
        return {}
    latest = max(period_cols)
    result = {}
    for _, row in em.iterrows():
        indicator = row.get("指标")
        if indicator is not None and str(indicator).strip():
            result[str(indicator)] = row.get(latest)
    result["数据来源"] = "东方财富"
    return result


def _profit_forecast_em(stock_code: str) -> list:
    """盈利预测回退源: 东方财富 (ak.stock_profit_forecast_em)。"""
    df = ak.stock_profit_forecast_em(symbol=stock_code)
    if df is None or df.empty:
        return []
    print(f"✅ 使用东方财富数据源获取 {stock_code} 盈利预测 ({len(df)} 条)")
    return df.head(5).to_dict(orient="records")


def _fund_flow_individual(stock_code: str) -> dict:
    """个股资金流回退源: 东方财富个股资金流历史接口 (与排名接口不同端点)。

    取最新一行并把列名统一为排名接口风格 (带 "今日" 前缀)。
    """
    market = "sh" if stock_code.startswith(("5", "6", "9")) else (
        "bj" if stock_code.startswith(("4", "8")) else "sz")
    df = ak.stock_individual_fund_flow(stock=stock_code, market=market)
    if df is None or df.empty:
        raise ValueError("个股资金流历史接口返回为空")
    row = df.iloc[-1].to_dict()
    result = {"代码": stock_code}
    column_map = {
        "名称": "名称", "收盘价": "最新价", "涨跌幅": "今日涨跌幅",
        "主力净流入-净额": "今日主力净流入-净额",
        "主力净流入-净占比": "今日主力净流入-净占比",
        "超大单净流入-净额": "今日超大单净流入-净额",
        "超大单净流入-净占比": "今日超大单净流入-净占比",
        "大单净流入-净额": "今日大单净流入-净额",
        "大单净流入-净占比": "今日大单净流入-净占比",
        "中单净流入-净额": "今日中单净流入-净额",
        "中单净流入-净占比": "今日中单净流入-净占比",
        "小单净流入-净额": "今日小单净流入-净额",
        "小单净流入-净占比": "今日小单净流入-净占比",
    }
    for src, dst in column_map.items():
        if src in row:
            result[dst] = row[src]
    result["数据状态"] = "正常"
    result["数据来源"] = "东方财富(个股资金流)"
    return result


def _fetch_10jqka_news(stock_code: str, limit: int = 15) -> list:
    """个股新闻回退源: 同花顺快讯 (tools/news_fetcher)。

    拉取全市场快讯后过滤出关联该股票的条目, 输出与东方财富新闻
    一致的字段: 新闻标题/发布时间/新闻内容/文章链接。
    """
    try:
        from tools.news_fetcher import get_10jqka_news
        items = get_10jqka_news(limit=100)
    except Exception as e:
        print(f"获取同花顺新闻失败: {e}")
        return []
    needle = f"({stock_code})"
    matched = []
    for it in items or []:
        stocks = it.get("stocks") or []
        if any(needle in str(s) for s in stocks):
            matched.append({
                "新闻标题": f"[同花顺] {it.get('title', '')}",
                "发布时间": f"{it.get('date', '')} {it.get('time', '')}".strip(),
                "新闻内容": it.get("content", ""),
                "文章链接": it.get("url", ""),
            })
    if matched:
        print(f"✅ 使用同花顺数据源获取 {stock_code} 新闻 ({len(matched)} 条)")
    return matched[:limit]


def _boards_industry() -> pd.DataFrame:
    """行业板块列表: 东方财富 -> 同花顺。保证含 板块名称 列。

    注意: 同花顺列表只有 name/code 两列 (无涨跌幅等行情字段),
    因此只适合"搜索板块名", 不适合做涨跌排序。
    """
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty and "板块名称" in df.columns:
            return df
        print("⚠️ 东方财富行业板块列表为空")
    except Exception as e:
        print(f"⚠️ 东方财富行业板块列表失败: {e}")
    try:
        df = ak.stock_board_industry_name_ths()
        if df is not None and not df.empty:
            rename = {"name": "板块名称", "code": "板块代码"}
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
            print(f"✅ 使用同花顺数据源获取行业板块列表 ({len(df)} 个)")
            return df
    except Exception as e:
        print(f"⚠️ 同花顺行业板块列表失败: {e}")
    return pd.DataFrame()


def _boards_concept() -> pd.DataFrame:
    """概念板块列表: 东方财富 -> 同花顺。保证含 板块名称 列。"""
    try:
        df = ak.stock_board_concept_name_em()
        if df is not None and not df.empty and "板块名称" in df.columns:
            return df
        print("⚠️ 东方财富概念板块列表为空")
    except Exception as e:
        print(f"⚠️ 东方财富概念板块列表失败: {e}")
    try:
        df = ak.stock_board_concept_name_ths()
        if df is not None and not df.empty:
            rename = {"name": "板块名称", "code": "板块代码"}
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
            print(f"✅ 使用同花顺数据源获取概念板块列表 ({len(df)} 个)")
            return df
    except Exception as e:
        print(f"⚠️ 同花顺概念板块列表失败: {e}")
    return pd.DataFrame()


def _board_summary_ths() -> pd.DataFrame:
    """同花顺行业板块涨跌摘要 (含 涨跌幅/领涨股/均价), 热门板块回退源。

    输出列名对齐东方财富: 板块名称/涨跌幅/领涨股票/最新价。
    """
    try:
        df = ak.stock_board_industry_summary_ths()
        if df is None or df.empty:
            return pd.DataFrame()
        rename = {"板块": "板块名称", "领涨股": "领涨股票", "均价": "最新价"}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        # 同花顺涨跌幅可能是字符串 (如 "4.07"), 统一转数值以便排序
        if "涨跌幅" in df.columns and not pd.api.types.is_numeric_dtype(df["涨跌幅"]):
            df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        print(f"✅ 使用同花顺数据源获取行业板块摘要 ({len(df)} 个)")
        return df
    except Exception as e:
        print(f"⚠️ 同花顺行业板块摘要失败: {e}")
        return pd.DataFrame()


# 东方财富/用户常用板块名 -> 同花顺行业指数名 (两套命名体系不同的常见对)
_EM_THS_BOARD_SYNONYMS = {
    "酿酒行业": "白酒",
    "饮料制造": "饮料制造",
    "汽车整车": "汽车整车",
}


def _ths_industry_name(board_name: str) -> Optional[str]:
    """把 (东方财富/用户) 板块名翻译为同花顺行业指数名, 找不到返回 None。

    同花顺行业指数使用自己的命名 (如 "白酒" vs 东方财富的 "酿酒行业"),
    因此先在其板块列表中做精确/包含式模糊匹配。
    """
    try:
        ths = ak.stock_board_industry_name_ths()
        if ths is None or ths.empty or "name" not in ths.columns:
            return None
        names = [str(n) for n in ths["name"].dropna().tolist() if str(n).strip()]
    except Exception as e:
        print(f"⚠️ 同花顺行业列表获取失败: {e}")
        return None
    if board_name in names:
        return board_name
    synonym = _EM_THS_BOARD_SYNONYMS.get(board_name)
    if synonym and synonym in names:
        return synonym
    stripped = board_name.replace("行业", "").replace("板块", "")
    candidates = [c for c in (board_name, stripped) if c]
    for n in names:
        for c in candidates:
            if n in c or c in n:
                return n
    return None


def _board_hist_em_or_ths(board_name: str, days: int = 150) -> pd.DataFrame:
    """行业板块日线: 东方财富 -> 同花顺 (stock_board_industry_index_ths)。"""
    try:
        df = ak.stock_board_industry_hist_em(symbol=board_name, adjust="qfq")
        if df is not None and not df.empty:
            return df
        print("⚠️ 东方财富行业板块K线为空")
    except Exception as e:
        print(f"⚠️ 东方财富行业板块K线失败: {e}")

    ths_name = _ths_industry_name(board_name)
    if not ths_name:
        print(f"⚠️ 同花顺行业指数中找不到与 {board_name} 匹配的板块")
        return pd.DataFrame()
    try:
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=max(days * 2 + 60, 260))).strftime("%Y%m%d")
        df = ak.stock_board_industry_index_ths(symbol=ths_name,
                                               start_date=start, end_date=end)
        if df is None or df.empty:
            return pd.DataFrame()
        rename = {"开盘价": "开盘", "最高价": "最高", "最低价": "最低",
                  "收盘价": "收盘"}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.sort_values("日期")
        print(f"✅ 使用同花顺数据源获取行业板块 {ths_name}({board_name}) K线 ({len(df)} 行)")
        return df.tail(days)
    except Exception as e:
        print(f"⚠️ 同花顺行业板块K线失败: {e}")
        return pd.DataFrame()

@ttl_cache(ttl_seconds=600)
@retry()
def get_stock_hist_data(stock_code: str, days: int = 150):
    """
    获取股票历史 K 线数据
    主源: 东方财富; 回退: 新浪 (不同数据源, 避免单源超时挂起)
    为保证技术指标（如 MA60）计算准确，默认获取 150 天数据
    缓存时间: 10 分钟
    """
    try:
        df = _fetch_hist_em(stock_code)
        if df.empty:
            df = _fetch_hist_sina(stock_code, days=days)
        if not df.empty:
            # 仅截取最近的 N 天用于返回，但保留足够的历史记录供计算
            return df.tail(days)
        return pd.DataFrame()
    except Exception as e:
        print(f"获取历史数据失败: {e}")
        return pd.DataFrame()

@ttl_cache(ttl_seconds=1800)
@retry()
def get_stock_financial_indicator(stock_code: str):
    """
    获取股票财务指标
    主源: 同花顺财务摘要; 回退: 东方财富财务摘要
    缓存时间: 30 分钟
    """
    try:
        df = ak.stock_financial_abstract_ths(symbol=stock_code)
        if df is not None and not df.empty:
            # 同花顺接口返回的数据通常按年份升序排列，取最后一行即为最新数据
            return df.iloc[-1].to_dict()
        print("⚠️ 同花顺财务摘要为空, 尝试东方财富...")
        return _financial_abstract_em(stock_code)
    except Exception as e:
        print(f"获取财务指标失败(同花顺): {e}, 尝试东方财富...")
        try:
            return _financial_abstract_em(stock_code)
        except Exception as e2:
            print(f"获取财务指标失败(东方财富): {e2}")
            return {}

def _parse_em_news(df: pd.DataFrame, limit: int = 15) -> list:
    """把东方财富个股新闻 DataFrame 解析为统一字段列表。"""
    if df is None or df.empty:
        return []
    available_cols = df.columns.tolist()
    mapping = {
        "新闻标题": ["新闻标题", "title", "标题"],
        "发布时间": ["发布时间", "time", "date", "时间"],
        "新闻内容": ["新闻内容", "content", "内容"],
        "文章链接": ["文章链接", "url", "link", "链接"],
    }
    final_mapping = {}
    for key, possible_names in mapping.items():
        for name in possible_names:
            if name in available_cols:
                final_mapping[key] = name
                break
    if "新闻标题" not in final_mapping:
        return []
    df_selected = df[list(final_mapping.values())].head(limit)
    df_selected.columns = list(final_mapping.keys())
    return df_selected.to_dict(orient="records")


@ttl_cache(ttl_seconds=300)
@retry()
def get_stock_news(stock_code: str, with_sector: bool = True):
    """
    获取个股新闻
    主源: 东方财富; 回退: 同花顺快讯 (按关联股票过滤)
    缓存时间: 5 分钟
    """
    try:
        df = ak.stock_news_em(symbol=stock_code)
        final_news = _parse_em_news(df)
        if not final_news:
            print("⚠️ 东方财富个股新闻为空, 尝试同花顺...")
            final_news = _fetch_10jqka_news(stock_code)
    except Exception as e:
        print(f"获取新闻失败(东方财富): {e}, 尝试同花顺...")
        final_news = _fetch_10jqka_news(stock_code)

    # 兜底逻辑：如果个股新闻少于 5 条，补充行业新闻
    if with_sector and len(final_news) < 5:
        try:
            # 获取行业
            info_df = ak.stock_individual_info_em(symbol=stock_code, timeout=_AK_TIMEOUT)
            if info_df is not None and not info_df.empty:
                industry_row = info_df[info_df["item"] == "行业"]
                if not industry_row.empty:
                    industry_name = industry_row.iloc[0]["value"]
                    # 注意：此处调用 get_board_news 时必须设置 with_stock=False，防止无限递归
                    sector_news = get_board_news(industry_name, "industry", with_stock=False)
                    # 标记为行业新闻
                    for item in sector_news:
                        item["新闻标题"] = f"[{industry_name}行业动态] {item['新闻标题']}"
                    final_news.extend(sector_news[:5])
        except Exception as e:
            print(f"获取个股关联行业新闻失败: {e}")

    return final_news

@ttl_cache(ttl_seconds=1800)
@retry()
def get_stock_report(stock_code: str):
    """
    获取个股盈利预测
    主源: 同花顺; 回退: 东方财富 (ak.stock_profit_forecast_em)
    缓存时间: 30 分钟
    """
    try:
        df = ak.stock_profit_forecast_ths(symbol=stock_code)
        if df is not None and not df.empty:
            # 同样确保取的是最新的预测数据
            return df.head(5).to_dict(orient="records")
        print("⚠️ 同花顺盈利预测为空, 尝试东方财富...")
        return _profit_forecast_em(stock_code)
    except Exception as e:
        print(f"获取盈利预测失败(同花顺): {e}, 尝试东方财富...")
        try:
            return _profit_forecast_em(stock_code)
        except Exception as e2:
            print(f"获取盈利预测失败(东方财富): {e2}")
            return []

@ttl_cache(ttl_seconds=300)
@retry()
def get_stock_fund_flow(stock_code: str):
    """
    获取个股资金流向 (AkShare - 东方财富排名接口)
    使用缓存以减少全市场排名接口的调用频率
    增强错误处理和回退机制
    缓存时间: 5 分钟
    """
    try:
        # 获取全市场排名
        df = ak.stock_individual_fund_flow_rank()
        if df is not None and not df.empty:
            # 过滤出当前股票
            row = df[df["代码"] == stock_code]
            if not row.empty:
                result = row.iloc[0].to_dict()
                result["数据状态"] = "正常"
                return result
            print(f"⚠️ 排名接口未找到股票 {stock_code}, 尝试个股资金流接口...")
        else:
            print("⚠️ 资金流向排名数据为空, 尝试个股资金流接口...")
    except Exception as e:
        print(f"获取资金流向失败(排名接口): {e}, 尝试个股资金流接口...")

    # 回退: 个股资金流历史接口 (东方财富另一端点, 取最新一行)
    try:
        return _fund_flow_individual(stock_code)
    except Exception as e:
        print(f"获取资金流向失败(个股接口): {e}")
        return {
            "代码": stock_code,
            "warning": f"获取资金流向失败: {str(e)[:50]}",
            "数据状态": "异常",
            "建议": "建议人工复核资金流向数据"
        }

@ttl_cache(ttl_seconds=3600)
@retry()
def search_board_info(name: str):
    """
    搜索板块信息 (行业或概念)
    缓存时间: 1 小时
    """
    try:
        # 1. 先查行业板块 (东方财富 -> 同花顺)
        ind_boards = _boards_industry()
        if not ind_boards.empty and "板块名称" in ind_boards.columns:
            match = ind_boards[ind_boards["板块名称"].str.contains(name, regex=False, na=False)]
            if not match.empty:
                return {"name": match.iloc[0]["板块名称"],
                        "code": match.iloc[0].get("板块代码", ""),
                        "type": "industry"}
        
        # 2. 再查概念板块 (东方财富 -> 同花顺)
        con_boards = _boards_concept()
        if not con_boards.empty and "板块名称" in con_boards.columns:
            match = con_boards[con_boards["板块名称"].str.contains(name, regex=False, na=False)]
            if not match.empty:
                return {"name": match.iloc[0]["板块名称"],
                        "code": match.iloc[0].get("板块代码", ""),
                        "type": "concept"}
            
        return None
    except Exception as e:
        print(f"搜索板块失败: {e}")
        return None

@ttl_cache(ttl_seconds=600)
@retry()
def get_board_hist_data(board_name: str, board_type: str = "industry", days: int = 150):
    """
    获取板块历史 K 线数据
    缓存时间: 10 分钟
    """
    try:
        if board_type == "industry":
            # 东方财富 -> 同花顺行业指数
            df = _board_hist_em_or_ths(board_name, days=days)
        else:
            df = ak.stock_board_concept_hist_em(symbol=board_name, adjust="qfq")
            
        if df is not None and not df.empty:
            if "日期" in df.columns:
                df["日期"] = pd.to_datetime(df["日期"])
                df = df.sort_values("日期")
            return df.tail(days)
        return pd.DataFrame()
    except Exception as e:
        print(f"获取板块历史数据失败: {e}")
        return pd.DataFrame()

@ttl_cache(ttl_seconds=3600)
@retry()
def get_board_cons(board_name: str, board_type: str = "industry"):
    """
    获取板块成分股
    缓存时间: 1 小时
    """
    try:
        if board_type == "industry":
            df = ak.stock_board_industry_cons_em(symbol=board_name)
        else:
            df = ak.stock_board_concept_cons_em(symbol=board_name)
        
        if not df.empty:
            return df.head(20).to_dict(orient="records") # 取前20名权重或核心股
        return []
    except Exception as e:
        print(f"获取板块成分股失败: {e}")
        return []

@ttl_cache(ttl_seconds=300)
@retry()
def get_board_news(board_name: str, board_type: str = "industry", with_stock: bool = True):
    """
    获取板块相关动态 (AkShare)
    with_stock: 是否通过成分股获取新闻，默认为 True
    缓存时间: 5 分钟
    """
    try:
        if not with_stock:
            # 如果不通过个股获取，目前 AkShare 缺乏直接的板块新闻接口，返回空或尝试全市场搜索
            return []

        # 1. 获取板块成分股
        cons = get_board_cons(board_name, board_type)
        if not cons:
            return []
            
        # 2. 获取前 5 个核心成分股的新闻
        all_news = []
        for stock in cons[:5]:
            stock_code = stock.get("代码") or stock.get("股票代码")
            if stock_code:
                # 注意：此处调用 get_stock_news 时必须设置 with_sector=False，防止无限递归
                news = get_stock_news(stock_code, with_sector=False)
                if news:
                    all_news.extend(news[:3]) 
                 
        # 去重处理
        unique_news = []
        seen_titles = set()
        for item in all_news:
            if item['新闻标题'] not in seen_titles:
                unique_news.append(item)
                seen_titles.add(item['新闻标题'])
                
        return unique_news[:15]
    except Exception as e:
        print(f"获取板块动态失败: {e}")
        return []

@ttl_cache(ttl_seconds=1800)
@retry()
def get_stock_industry_comparison(stock_code: str):
    """
    获取股票所属行业的对比数据 (AkShare)
    增强错误处理和回退机制
    添加缓存以减少重复调用
    缓存时间: 30 分钟
    """
    board_name = None
    
    try:
        # 1. 尝试通过个股信息接口直接获取行业名称
        info_df = ak.stock_individual_info_em(symbol=stock_code, timeout=_AK_TIMEOUT)
        if info_df is not None and not info_df.empty:
            industry_row = info_df[info_df["item"] == "行业"]
            if not industry_row.empty:
                board_name = industry_row.iloc[0]["value"]
        
        if not board_name:
            print(f"⚠️ 无法获取股票 {stock_code} 的行业信息")
            return {
                "error": "无法获取行业信息",
                "stock_code": stock_code,
                "warning": "行业对比数据暂不可用，建议人工复核",
                "数据状态": "缺失"
            }

    except Exception as e:
        print(f"⚠️ 获取股票 {stock_code} 行业信息失败: {e}")
        return {
            "error": f"获取行业信息失败: {str(e)}",
            "stock_code": stock_code,
            "warning": "行业对比数据暂不可用，建议人工复核",
            "数据状态": "异常"
        }

    # 尝试多个数据源获取行业对比数据
    comparison_data = None
    
    # 尝试 1: 东方财富行业板块摘要
    try:
        df = ak.stock_board_industry_summary_ths()
        if df is not None and not df.empty:
            # 尝试精确匹配
            match = df[df["板块"] == board_name]
            if match.empty:
                # 如果精确匹配失败，尝试模糊匹配
                match = df[df["板块"].str.contains(board_name, regex=False, na=False)]
            
            if not match.empty:
                comparison_data = match.iloc[0].to_dict()
                comparison_data["数据来源"] = "东方财富"
                comparison_data["行业名称"] = board_name
                comparison_data["数据状态"] = "正常"
                return comparison_data
    except Exception as e:
        print(f"⚠️ 东方财富行业数据获取失败: {e}")
    
    # 尝试 2: 行业板块列表 (东方财富 -> 同花顺)
    try:
        df = _boards_industry()
        if df is not None and not df.empty:
            # 尝试匹配行业名称
            match = df[df["板块名称"] == board_name]
            if match.empty:
                match = df[df["板块名称"].str.contains(board_name, regex=False, na=False)]
            
            if not match.empty:
                comparison_data = {
                    "行业名称": board_name,
                    "板块名称": match.iloc[0]["板块名称"],
                    "最新价": match.iloc[0].get("最新价", "N/A"),
                    "涨跌幅": match.iloc[0].get("涨跌幅", "N/A"),
                    "涨跌额": match.iloc[0].get("涨跌额", "N/A"),
                    "成交量": match.iloc[0].get("成交量", "N/A"),
                    "成交额": match.iloc[0].get("成交额", "N/A"),
                    "数据来源": "同花顺",
                    "数据状态": "正常"
                }
                return comparison_data
    except Exception as e:
        print(f"⚠️ 同花顺行业数据获取失败: {e}")
    
    # 尝试 3: 获取行业内个股排名（作为替代指标）
    try:
        df = ak.stock_board_industry_cons_em(symbol=board_name)
        if df is not None and not df.empty:
            comparison_data = {
                "行业名称": board_name,
                "成分股数量": len(df),
                "数据来源": "成分股统计",
                "数据状态": "部分可用",
                "说明": "仅获取到行业成分股信息，无法获取行业整体指标"
            }
            return comparison_data
    except Exception as e:
        print(f"⚠️ 行业成分股数据获取失败: {e}")
    
    # 所有尝试都失败，返回基本信息
    print(f"⚠️ 所有行业对比数据源均不可用")
    return {
        "行业名称": board_name,
        "warning": "行业对比数据暂不可用，已尝试多个数据源但均失败",
        "数据状态": "缺失",
        "建议": "建议人工复核行业对比数据",
        "数据来源": "无"
    }

@ttl_cache(ttl_seconds=3600)
@retry()
def get_stock_valuation_history(stock_code: str, days: int = 250):
    """
    获取股票历史估值数据 (PE, PB, PS等)
    返回历史分位点等信息
    """
    try:
        df = pd.DataFrame()
        # 尝试获取历史估值 (乐咕乐股)
        if hasattr(ak, "stock_a_indicator_lg"):
            try:
                df = ak.stock_a_indicator_lg(symbol=stock_code)
            except Exception:
                pass
        
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date')
            
            latest = df.iloc[-1]
            history = df.tail(days)
            
            # 计算分位点
            pe_percentile = (df['pe'] < latest['pe']).mean() * 100
            pb_percentile = (df['pb'] < latest['pb']).mean() * 100
            
            return {
                "latest_pe": latest['pe'],
                "pe_percentile": pe_percentile,
                "latest_pb": latest['pb'],
                "pb_percentile": pb_percentile,
                "history": history.to_dict(orient="records")
            }
        
        # Fallback: 如果无法获取历史数据，仅获取当前数据
        # (全市场快照: 东方财富 -> 新浪)
        spot_df = _get_spot_snapshot()
        if not spot_df.empty:
            match = spot_df[spot_df["代码"] == stock_code]
            if not match.empty:
                row = match.iloc[0]
                pe = row.get("市盈率-动态", 0)
                pb = row.get("市净率", 0)
                return {
                    "latest_pe": pe,
                    "pe_percentile": 50.0, # 无法计算分位，给默认值
                    "latest_pb": pb,
                    "pb_percentile": 50.0,
                    "history": []
                }
                
        return {}
    except Exception as e:
        print(f"获取估值历史失败: {e}")
        return {}

@ttl_cache(ttl_seconds=1800)
@retry()
def get_market_sentiment():
    """
    获取市场情绪指标 (如全市场涨跌停家数、换手率等)
    """
    try:
        # 获取 A 股实时行情摘要作为情绪代理 (东方财富 -> 新浪)
        df = _get_spot_snapshot()
        if not df.empty:
            up = len(df[df["涨跌幅"] > 0])
            down = len(df[df["涨跌幅"] < 0])
            limit_up = len(df[df["涨跌幅"] >= 9.8])
            limit_down = len(df[df["涨跌幅"] <= -9.8])
            
            total = len(df)
            breadth = up / total if total > 0 else 0
            
            return {
                "上涨家数": up,
                "下跌家数": down,
                "涨停家数": limit_up,
                "跌停家数": limit_down,
                "市场宽度": breadth,
                "情绪描述": "极度乐观" if breadth > 0.8 else "乐观" if breadth > 0.6 else "中性" if breadth > 0.4 else "悲观" if breadth > 0.2 else "极度悲观"
            }
        return {}
    except Exception as e:
        print(f"获取市场情绪失败: {e}")
        return {}

def _pick_index_rows(df: pd.DataFrame, name_col: str, price_col: str,
                      change_col: str, pct_col: str) -> list:
    """从指数快照 DataFrame 中提取目标指数行。"""
    target_indices = ["上证指数", "深证成指", "创业板指", "科创50"]
    results = []
    for name in target_indices:
        match = df[df[name_col].str.contains(name, na=False)]
        if not match.empty:
            row = match.iloc[0]
            results.append({
                "name": name,
                "price": row.get(price_col),
                "change": row.get(change_col),
                "change_pct": row.get(pct_col),
            })
    return results

@ttl_cache(ttl_seconds=60)
@retry()
def get_market_indices():
    """
    获取主要指数实时行情 (上证, 深证, 创业板, 科创50)
    主源: 新浪; 回退: 东方财富
    """
    try:
        # 使用新浪实时指数接口，覆盖面更广
        df = ak.stock_zh_index_spot_sina()
        if df is not None and not df.empty:
            # 映射可能的列名 (由于编码问题，尝试匹配包含关键字的列)
            name_col = next((c for c in df.columns if "名称" in c or "鍚嶇О" in c), "名称")
            price_col = next((c for c in df.columns if "最新价" in c or "鏈€鏂颁环" in c), "最新价")
            change_col = next((c for c in df.columns if "涨跌额" in c or "娑ㄨ穼棰" in c), "涨跌额")
            pct_col = next((c for c in df.columns if "涨跌幅" in c or "娑ㄨ穼骞" in c), "涨跌幅")
            results = _pick_index_rows(df, name_col, price_col, change_col, pct_col)
            if results:
                return results
        print("⚠️ 新浪指数行情为空, 尝试东方财富...")
    except Exception as e:
        print(f"获取指数行情失败(新浪): {e}, 尝试东方财富...")

    try:
        # 回退: 东方财富指数行情
        em = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
        if em is not None and not em.empty:
            results = _pick_index_rows(em, "名称", "最新价", "涨跌额", "涨跌幅")
            if results:
                print(f"✅ 使用东方财富数据源获取指数行情 ({len(results)} 项)")
                return results
    except Exception as e:
        print(f"获取指数行情失败(东方财富): {e}")
    return []

@ttl_cache(ttl_seconds=300)
@retry()
def get_market_hot_sectors(limit: int = 5):
    """
    获取领涨行业板块
    """
    try:
        # 行业板块列表 (东方财富), 无行情字段时回退同花顺板块摘要
        df = _boards_industry()
        if df.empty or "涨跌幅" not in df.columns:
            df = _board_summary_ths()
        if not df.empty and "涨跌幅" in df.columns:
            if "领涨股" in df.columns and "领涨股票" not in df.columns:
                df = df.rename(columns={"领涨股": "领涨股票"})
            if "板块指数" in df.columns and "最新价" not in df.columns:
                df = df.rename(columns={"板块指数": "最新价"})
            # 按涨跌幅排序
            df = df.sort_values("涨跌幅", ascending=False).head(limit)
            cols = [c for c in ["板块名称", "涨跌幅", "领涨股票", "最新价"] if c in df.columns]
            return df[cols].to_dict(orient="records")
        return []
    except Exception as e:
        print(f"获取热门板块失败: {e}")
        return []

@ttl_cache(ttl_seconds=3600)
@retry()
def search_stock_code(stock_name: str):
    """
    通过股票名称搜索股票代码 (AkShare)
    缓存时间: 1 小时
    """
    try:
        # 全市场快照 (东方财富 -> 新浪)
        df = _get_spot_snapshot()
        if not df.empty and "名称" in df.columns:
            match = df[df["名称"].str.contains(stock_name, regex=False, na=False)]
            if not match.empty:
                return match.iloc[0]["代码"], match.iloc[0]["名称"]
        return None, None
    except Exception as e:
        print(f"搜索股票代码失败: {e}")
        return None, None
