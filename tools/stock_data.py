import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from functools import wraps, lru_cache
import json
import os
import hashlib
from typing import Any, Callable, Optional, Dict, Union

def retry(max_retries=3, delay=1, backoff=2):
    """
    重试装饰器，用于 AkShare 接口请求
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        print(f"❌ {func.__name__} 达到最大重试次数: {e}")
                        raise e
                    print(f"⚠️ {func.__name__} 请求失败 (第 {retries} 次): {e}, {current_delay}s 后重试...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

class TTLCache:
    """
    文件持久化的 TTL 缓存
    """
    def __init__(self, cache_file: str = ".akshare_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """加载缓存文件"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 处理 DataFrame 反序列化
                deserialized_cache = {}
                for key, entry in cache_data.items():
                    deserialized_entry = {}
                    for k, v in entry.items():
                        if k == 'data' and isinstance(v, dict) and v.get('type') == 'DataFrame':
                            # 将字典转换回 DataFrame
                            df_data = v.get('data', [])
                            # 将 ISO 格式字符串转换回 Timestamp
                            processed_data = []
                            for row in df_data:
                                processed_row = {}
                                for col_key, col_value in row.items():
                                    # 尝试将字符串转换为 Timestamp
                                    if isinstance(col_value, str):
                                        try:
                                            # 尝试解析为日期时间
                                            processed_row[col_key] = pd.to_datetime(col_value)
                                        except:
                                            # 如果解析失败，保持原样
                                            processed_row[col_key] = col_value
                                    else:
                                        processed_row[col_key] = col_value
                                processed_data.append(processed_row)
                            
                            deserialized_entry[k] = pd.DataFrame(processed_data)
                        else:
                            deserialized_entry[k] = v
                    deserialized_cache[key] = deserialized_entry
                
                return deserialized_cache
            except Exception as e:
                print(f"⚠️ 加载缓存文件失败: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """保存缓存到文件"""
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
        """设置缓存"""
        key = self._generate_key(func_name, args, kwargs)
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'function': func_name
        }
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

def ttl_cache(ttl_seconds: int = 300):
    """
    TTL 缓存装饰器
    ttl_seconds: 缓存过期时间（秒），默认 5 分钟
    """
    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从缓存获取
            cached_data, timestamp = _cache_instance.get(func_name, args, kwargs)
            
            if cached_data is not None:
                try:
                    cache_time = datetime.fromisoformat(timestamp)
                    if (datetime.now() - cache_time).total_seconds() < ttl_seconds:
                        print(f"✅ {func_name} 使用缓存 (更新于: {timestamp})")
                        return cached_data
                except Exception as e:
                    print(f"⚠️ 缓存时间解析失败: {e}")
            
            # 缓存未命中或已过期，调用原函数
            result = func(*args, **kwargs)
            
            # 保存到缓存
            if result is not None:
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

@ttl_cache(ttl_seconds=600)
@retry()
def get_stock_hist_data(stock_code: str, days: int = 150):
    """
    获取股票历史 K 线数据 (AkShare)
    为保证技术指标（如 MA60）计算准确，默认获取 150 天数据
    缓存时间: 10 分钟
    """
    try:
        # 获取足够的历史数据以支持指标计算
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if not df.empty:
            df['日期'] = pd.to_datetime(df['日期'])
            # 排序确保日期递增
            df = df.sort_values('日期')
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
    获取股票财务指标 (AkShare - 同花顺财务摘要)
    缓存时间: 30 分钟
    """
    try:
        df = ak.stock_financial_abstract_ths(symbol=stock_code)
        if not df.empty:
            # 同花顺接口返回的数据通常按年份升序排列，取最后一行即为最新数据
            return df.iloc[-1].to_dict()
        return {}
    except Exception as e:
        print(f"获取财务指标失败: {e}")
        return {}

@ttl_cache(ttl_seconds=300)
@retry()
def get_stock_news(stock_code: str, with_sector: bool = True):
    """
    获取东方财富个股新闻
    缓存时间: 5 分钟
    """
    try:
        df = ak.stock_news_em(symbol=stock_code)
        
        final_news = []
        if not df.empty:
            available_cols = df.columns.tolist()
            mapping = {
                "新闻标题": ["新闻标题", "title", "标题"],
                "发布时间": ["发布时间", "time", "date", "时间"],
                "新闻内容": ["新闻内容", "content", "内容"],
                "文章链接": ["文章链接", "url", "link", "链接"]
            }
            
            final_mapping = {}
            for key, possible_names in mapping.items():
                for name in possible_names:
                    if name in available_cols:
                        final_mapping[key] = name
                        break
            
            if "新闻标题" in final_mapping:
                df_selected = df[list(final_mapping.values())].head(15)
                df_selected.columns = list(final_mapping.keys())
                final_news = df_selected.to_dict(orient="records")
        
        # 兜底逻辑：如果个股新闻少于 5 条，补充行业新闻
        if with_sector and len(final_news) < 5:
            try:
                # 获取行业
                info_df = ak.stock_individual_info_em(symbol=stock_code)
                if not info_df.empty:
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
    except Exception as e:
        print(f"获取新闻失败: {e}")
        return []

@ttl_cache(ttl_seconds=1800)
@retry()
def get_stock_report(stock_code: str):
    """
    获取个股盈利预测 (AkShare - 同花顺)
    缓存时间: 30 分钟
    """
    try:
        df = ak.stock_profit_forecast_ths(symbol=stock_code)
        if not df.empty:
            # 同样确保取的是最新的预测数据
            return df.head(5).to_dict(orient="records")
        return []
    except Exception as e:
        print(f"获取盈利预测失败: {e}")
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
            else:
                print(f"⚠️ 未找到股票 {stock_code} 的资金流向数据")
                return {
                    "代码": stock_code,
                    "warning": "未找到该股票的资金流向数据",
                    "数据状态": "缺失",
                    "建议": "建议人工复核资金流向数据"
                }
        else:
            print(f"⚠️ 资金流向数据为空")
            return {
                "代码": stock_code,
                "warning": "资金流向数据暂不可用",
                "数据状态": "异常",
                "建议": "建议人工复核资金流向数据"
            }
    except Exception as e:
        print(f"获取资金流向失败: {e}")
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
        # 1. 先查行业板块
        ind_boards = ak.stock_board_industry_name_em()
        match = ind_boards[ind_boards["板块名称"].str.contains(name, regex=False, na=False)]
        if not match.empty:
            return {"name": match.iloc[0]["板块名称"], "code": match.iloc[0]["板块代码"], "type": "industry"}
        
        # 2. 再查概念板块
        con_boards = ak.stock_board_concept_name_em()
        match = con_boards[con_boards["板块名称"].str.contains(name, regex=False, na=False)]
        if not match.empty:
            return {"name": match.iloc[0]["板块名称"], "code": match.iloc[0]["板块代码"], "type": "concept"}
            
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
            df = ak.stock_board_industry_hist_em(symbol=board_name, adjust="qfq")
        else:
            df = ak.stock_board_concept_hist_em(symbol=board_name, adjust="qfq")
            
        if not df.empty:
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期')
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
        info_df = ak.stock_individual_info_em(symbol=stock_code)
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
    
    # 尝试 2: 同花顺行业板块数据
    try:
        df = ak.stock_board_industry_name_em()
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
def search_stock_code(stock_name: str):
    """
    通过股票名称搜索股票代码 (AkShare)
    缓存时间: 1 小时
    """
    try:
        df = ak.stock_zh_a_spot_em()
        if not df.empty:
            match = df[df["名称"].str.contains(stock_name, regex=False, na=False)]
            if not match.empty:
                return match.iloc[0]["代码"], match.iloc[0]["名称"]
        return None, None
    except Exception as e:
        print(f"搜索股票代码失败: {e}")
        return None, None
