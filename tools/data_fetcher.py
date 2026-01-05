import akshare as ak
import pandas as pd
import time
from typing import Dict, Any, Optional, Callable, TypeVar
from datetime import datetime, timedelta
from .data_cache import DataCache
from .logger import logger
from .performance_monitor import performance_monitor
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import re
import concurrent.futures

T = TypeVar('T')

def run_with_timeout(func: Callable[..., T], timeout: float, default: T = None) -> T:
    """执行函数并添加超时控制（兼容eventlet）"""
    try:
        import eventlet
        from eventlet.timeout import Timeout
        
        def _wrapper():
            try:
                return func()
            except Exception as e:
                logger.warning(f"[错误] 函数执行失败: {func.__name__}, 错误: {str(e)}")
                return default
        
        with Timeout(timeout, False):
            return eventlet.spawn(_wrapper).wait()
        
        logger.warning(f"[超时] 函数执行超时（{timeout}秒）: {func.__name__}")
        return default
    except ImportError:
        # 如果没有eventlet，使用原生的ThreadPoolExecutor
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning(f"[超时] 函数执行超时（{timeout}秒）: {func.__name__}")
            return default
        except Exception as e:
            logger.warning(f"[错误] 函数执行失败: {func.__name__}, 错误: {str(e)}")
            return default

# 设置全局请求超时和重试策略
session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 设置全局超时时间
GLOBAL_TIMEOUT = 30  # 30秒超时
SPOT_CACHE_TTL = 10
STOCK_LIST_TTL = 86400

_spot_cache_lock = threading.Lock()
_spot_cache_df: Optional[pd.DataFrame] = None
_spot_cache_ts: float = 0.0

_stock_list_cache_lock = threading.Lock()
_stock_list_cache_df: Optional[pd.DataFrame] = None
_stock_list_cache_ts: float = 0.0
_stock_list_fetching: bool = False

def _infer_market(stock_code: str) -> str:
    if isinstance(stock_code, str) and stock_code.startswith("6"):
        return "sh"
    return "sz"

def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).strip().replace(",", "")
        if s == "":
            return None
        return float(s)
    except Exception:
        return None

class DataFetcher:
    def __init__(self, enable_cache: bool = True):
        self.cache = DataCache() if enable_cache else None
        try:
            self._get_stock_list_data()
        except Exception:
            pass
    
    def _get_spot_data(self) -> pd.DataFrame:
        global _spot_cache_df, _spot_cache_ts
        now = time.time()
        with _spot_cache_lock:
            if _spot_cache_df is not None and (now - _spot_cache_ts) < SPOT_CACHE_TTL:
                return _spot_cache_df
        
        df = run_with_timeout(
            lambda: ak.stock_zh_a_spot_em(),
            timeout=10.0,
            default=None
        )
        if df is None:
            logger.warning("[超时] 获取实时行情数据超时，返回空DataFrame")
            return pd.DataFrame()
        
        with _spot_cache_lock:
            _spot_cache_df = df
            _spot_cache_ts = now
        return df

    def _peek_spot_cache(self) -> Optional[pd.DataFrame]:
        global _spot_cache_df, _spot_cache_ts
        now = time.time()
        with _spot_cache_lock:
            if _spot_cache_df is not None and (now - _spot_cache_ts) < SPOT_CACHE_TTL:
                return _spot_cache_df
        return None

    def _get_stock_list_data(self) -> Optional[pd.DataFrame]:
        global _stock_list_cache_df, _stock_list_cache_ts, _stock_list_fetching
        now = time.time()
        with _stock_list_cache_lock:
            if _stock_list_cache_df is not None and (now - _stock_list_cache_ts) < STOCK_LIST_TTL:
                return _stock_list_cache_df

        if self.cache:
            cached = self.cache.get("stock_list", {})
            if cached:
                try:
                    df = pd.DataFrame(cached)
                    with _stock_list_cache_lock:
                        _stock_list_cache_df = df
                        _stock_list_cache_ts = now
                    return df
                except Exception:
                    pass

        with _stock_list_cache_lock:
            if _stock_list_fetching:
                return None
            _stock_list_fetching = True

        def _build():
            global _stock_list_cache_df, _stock_list_cache_ts, _stock_list_fetching
            try:
                df = ak.stock_info_a_code_name()
                if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                    return
                with _stock_list_cache_lock:
                    _stock_list_cache_df = df
                    _stock_list_cache_ts = time.time()
                if self.cache:
                    try:
                        self.cache.set("stock_list", {}, df.to_dict("records"), ttl=STOCK_LIST_TTL)
                    except Exception:
                        pass
            finally:
                with _stock_list_cache_lock:
                    _stock_list_fetching = False

        threading.Thread(target=_build, daemon=True).start()
        return None

    def _get_stock_info_from_individual(self, stock_code: str) -> Optional[Dict[str, Any]]:
        df = ak.stock_individual_info_em(symbol=stock_code)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return None
        if not {"item", "value"}.issubset(set(df.columns)):
            return None

        kv = dict(zip(df["item"].astype(str), df["value"]))
        stock_name = kv.get("股票简称") or kv.get("股票名称") or ""
        current_price = kv.get("最新") or kv.get("最新价") or kv.get("当前价格") or ""
        total_shares = kv.get("总股本") or ""
        float_shares = kv.get("流通股") or ""
        industry = kv.get("所属行业") or ""
        main_business = kv.get("主营业务") or ""

        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "current_price": _to_float(current_price) if _to_float(current_price) is not None else current_price,
            "market_cap": "",
            "pe_ratio": "",
            "pb_ratio": "",
            "turnover_rate": "",
            "volume_ratio": "",
            "high_52w": "",
            "low_52w": "",
            "total_shares": _to_float(total_shares) if _to_float(total_shares) is not None else total_shares,
            "float_shares": _to_float(float_shares) if _to_float(float_shares) is not None else float_shares,
            "industry": industry,
            "main_business": main_business,
            "timestamp": datetime.now().isoformat(),
        }

        spot_df = self._peek_spot_cache()
        if spot_df is not None and not spot_df.empty and "代码" in spot_df.columns:
            try:
                row = spot_df[spot_df["代码"] == stock_code]
                if not row.empty:
                    stock = row.iloc[0]
                    result["stock_name"] = result["stock_name"] or stock.get("名称", "")
                    if result["current_price"] in ("", None):
                        result["current_price"] = stock.get("最新价", "")
                    result["market_cap"] = stock.get("总市值", "")
                    result["pe_ratio"] = stock.get("市盈率-动态", "")
                    result["pb_ratio"] = stock.get("市净率", "")
                    result["turnover_rate"] = stock.get("换手率", "")
                    result["volume_ratio"] = stock.get("量比", "")
            except Exception:
                pass

        return result
    
    @performance_monitor
    def get_stock_info(self, stock_code: str) -> Dict[str, Any]:
        if self.cache:
            cached_data = self.cache.get('stock_info', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取股票信息缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取股票信息: {stock_code}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = self._get_stock_info_from_individual(stock_code)
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取股票信息超时")
                
                if result is None:
                    spot_data = self._get_spot_data()
                    if spot_data is None or spot_data.empty:
                        raise Exception("无法获取股票信息：返回数据为空")
                    
                    stock_row = spot_data[spot_data['代码'] == stock_code]
                    
                    if stock_row.empty:
                        raise Exception(f"无法获取股票信息：未找到股票代码 {stock_code}")
                    
                    stock = stock_row.iloc[0]
                    
                    result = {
                        'stock_code': stock_code,
                        'stock_name': stock.get('名称', ''),
                        'current_price': stock.get('最新价', 0.0),
                        'change': stock.get('涨跌额', 0.0),
                        'change_percent': stock.get('涨跌幅', 0.0),
                        'volume': stock.get('成交量', 0.0),
                        'amount': stock.get('成交额', 0.0),
                        'market_cap': stock.get('总市值', ''),
                        'pe_ratio': stock.get('市盈率-动态', ''),
                        'pb_ratio': stock.get('市净率', ''),
                        'turnover_rate': stock.get('换手率', ''),
                        'volume_ratio': stock.get('量比', ''),
                        'high_52w': '',
                        'low_52w': '',
                        'industry': '',
                        'main_business': '',
                        'timestamp': datetime.now().isoformat()
                    }
                
                if self.cache:
                    self.cache.set('stock_info', {'stock_code': stock_code}, result)
                    logger.info(f"[数据缓存] 股票信息已缓存: {stock_code}")
                
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取股票信息失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    raise Exception(f"获取股票信息失败: {str(e)}")
                logger.warning(f"[数据获取] 获取股票信息失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                retry_delay *= 1.5
    
    @performance_monitor
    def get_kline_data(self, stock_code: str, period: str = 'daily', count: int = 120) -> pd.DataFrame:
        if self.cache:
            cached_data = self.cache.get('kline_data', {'stock_code': stock_code, 'period': period, 'count': count})
            if cached_data and isinstance(cached_data, list) and len(cached_data) > 0:
                logger.info(f"[数据缓存] 获取K线数据缓存命中: {stock_code}, 周期: {period}, 数量: {count}")
                try:
                    return pd.DataFrame(cached_data)
                except Exception as e:
                    logger.warning(f"[数据缓存] 缓存数据转换失败: {e}")
        
        logger.info(f"[数据获取] 开始获取K线数据: {stock_code}, 周期: {period}, 数量: {count}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=count * 2)).strftime('%Y%m%d')
                
                start_time = time.time()
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取K线数据超时")
                
                if df is None or df.empty:
                    logger.info(f"[数据获取] K线数据为空: {stock_code}, 周期: {period}")
                    return pd.DataFrame()
                
                result = df.tail(count)
                
                if self.cache:
                    try:
                        cache_df = result.copy()
                        if isinstance(cache_df, pd.DataFrame) and '日期' in cache_df.columns:
                            cache_df['日期'] = cache_df['日期'].astype(str)
                        self.cache.set('kline_data', {'stock_code': stock_code, 'period': period, 'count': count}, cache_df.to_dict('records'))
                        logger.info(f"[数据缓存] K线数据已缓存: {stock_code}, 周期: {period}, 数量: {count}")
                    except Exception as e:
                        logger.warning(f"[数据缓存] 缓存K线数据失败: {e}")
                
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取K线数据失败 (尝试{max_retries}次): {stock_code}, 周期: {period}, 错误: {str(e)}")
                    raise Exception(f"获取K线数据失败: {str(e)}")
                logger.warning(f"[数据获取] 获取K线数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 周期: {period}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))
                retry_delay *= 1.5
    
    @performance_monitor
    def get_financial_data(self, stock_code: str) -> Dict[str, Any]:
        if self.cache:
            cached_data = self.cache.get('financial_data', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取财务数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取财务数据: {stock_code}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                financial_abstract = ak.stock_financial_abstract(symbol=stock_code)
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取财务数据超时")
                
                if financial_abstract is None or financial_abstract.empty:
                    logger.info(f"[数据获取] 财务数据为空: {stock_code}")
                    result = {}
                else:
                    date_cols = [c for c in financial_abstract.columns if re.fullmatch(r"\d{8}", str(c))]
                    if date_cols:
                        latest_col = max(date_cols, key=lambda x: str(x))
                    else:
                        latest_col = financial_abstract.columns[-1]
                    
                    def get_indicator_value(indicator_name: str) -> str:
                        try:
                            row = financial_abstract[financial_abstract['指标'] == indicator_name]
                            if not row.empty:
                                value = row.iloc[0][latest_col]
                                if pd.notna(value):
                                    return str(value)
                        except Exception:
                            pass
                        return ''
                    
                    result = {
                        'roe': get_indicator_value('净资产收益率(ROE)'),
                        'roa': get_indicator_value('总资产报酬率(ROA)'),
                        'gross_margin': get_indicator_value('毛利率'),
                        'net_margin': get_indicator_value('销售净利率'),
                        'debt_ratio': get_indicator_value('资产负债率'),
                        'current_ratio': get_indicator_value('流动比率'),
                        'revenue_growth': get_indicator_value('营业总收入增长率'),
                        'profit_growth': get_indicator_value('归属母公司净利润增长率'),
                        # 新增运营能力指标
                        'inventory_turnover': get_indicator_value('存货周转率'),
                        'accounts_receivable_turnover': get_indicator_value('应收账款周转率'),
                        'total_asset_turnover': get_indicator_value('总资产周转率'),
                        # 新增现金流指标
                        'operating_cash_flow': get_indicator_value('经营活动产生的现金流量净额'),
                        'operating_cash_flow_per_share': get_indicator_value('经营活动产生的现金流量净额/基本每股收益'),
                        'cash_flow_ratio': get_indicator_value('经营活动产生的现金流量净额/负债合计'),
                        # 新增每股指标
                        'eps': get_indicator_value('基本每股收益'),
                        'book_value_per_share': get_indicator_value('每股净资产'),
                        'cash_per_share': get_indicator_value('每股经营活动产生的现金流量净额'),
                        # 新增盈利能力补充指标
                        'operating_profit_margin': get_indicator_value('营业利润率'),
                        'return_on_operating_assets': get_indicator_value('营业总成本/营业总收入'),
                        # 新增成长能力补充指标
                        'operating_revenue_growth': get_indicator_value('营业收入增长率'),
                        'operating_profit_growth': get_indicator_value('营业利润增长率')
                    }
                    logger.debug(f"[数据获取] 解析财务数据成功: {stock_code}")
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取股票信息失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    raise Exception(f"获取股票信息失败: {str(e)}")
                logger.warning(f"[数据获取] 获取股票信息失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                retry_delay *= 1.5
            
            if self.cache:
                self.cache.set('financial_data', {'stock_code': stock_code}, result)
                logger.info(f"[数据缓存] 财务数据已缓存: {stock_code}")
            
            return result
    
    @performance_monitor
    def get_fund_flow(self, stock_code: str) -> Dict[str, Any]:
        if self.cache:
            cached_data = self.cache.get('fund_flow', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取资金流向数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取资金流向数据: {stock_code}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                market = _infer_market(stock_code)
                fund_flow = ak.stock_individual_fund_flow(stock=stock_code, market=market)
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取资金流向数据超时")
                
                if fund_flow is None or not isinstance(fund_flow, pd.DataFrame) or fund_flow.empty:
                    logger.info(f"[数据获取] 资金流向数据为空: {stock_code}")
                    result = {}
                else:
                    try:
                        latest = fund_flow.iloc[-1].to_dict()
                        result = {
                            'main_net_inflow': latest.get('主力净流入-净额', ''),
                            'main_net_inflow_pct': latest.get('主力净流入-净占比', ''),
                            'super_large_net_inflow': latest.get('超大单净流入-净额', ''),
                            'large_net_inflow': latest.get('大单净流入-净额', ''),
                            'medium_net_inflow': latest.get('中单净流入-净额', ''),
                            'small_net_inflow': latest.get('小单净流入-净额', '')
                        }
                        logger.debug(f"[数据获取] 解析资金流向成功: {stock_code}, 日期: {latest.get('日期', '')}")
                    except Exception as e:
                        logger.error(f"[数据获取] 解析资金流向失败: {stock_code}, 错误: {str(e)}")
                        result = {}
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取资金流向数据失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    return {}
                logger.warning(f"[数据获取] 获取资金流向数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                retry_delay *= 1.5
                continue
            
            if self.cache:
                self.cache.set('fund_flow', {'stock_code': stock_code}, result)
                logger.info(f"[数据缓存] 资金流向数据已缓存: {stock_code}")
            
            return result
    
    @performance_monitor
    def get_market_sentiment(self) -> Dict[str, Any]:
        if self.cache:
            cached_data = self.cache.get('market_sentiment', {})
            if cached_data:
                logger.info(f"[数据缓存] 获取市场情绪数据缓存命中")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取市场情绪数据")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                market_sentiment = ak.stock_market_activity_legu()
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取市场情绪数据超时")
                
                if market_sentiment is None:
                    logger.info(f"[数据获取] 市场情绪数据为None")
                    # 返回默认结果
                    result = {
                        'up_count': 0,
                        'down_count': 0,
                        'flat_count': 0,
                        'total_count': 0,
                        'up_down_ratio': 0,
                        'market_heat': 0,
                        'activity_level': '0%',
                        'limit_up_count': 0,
                        'limit_down_count': 0
                    }
                elif isinstance(market_sentiment, pd.DataFrame):
                    if market_sentiment.empty:
                        logger.info(f"[数据获取] 市场情绪数据为空DataFrame")
                        # 返回默认结果
                        result = {
                            'up_count': 0,
                            'down_count': 0,
                            'flat_count': 0,
                            'total_count': 0,
                            'up_down_ratio': 0,
                            'market_heat': 0,
                            'activity_level': '0%',
                            'limit_up_count': 0,
                            'limit_down_count': 0
                        }
                    else:
                        try:
                            sentiment_dict = {}
                            for _, row in market_sentiment.iterrows():
                                if 'item' in row and 'value' in row:
                                    sentiment_dict[row['item']] = row['value']
                        except Exception as e:
                            logger.error(f"[数据获取] 解析市场情绪DataFrame失败: 错误: {str(e)}")
                            # 返回默认结果
                            result = {
                                'up_count': 0,
                                'down_count': 0,
                                'flat_count': 0,
                                'total_count': 0,
                                'up_down_ratio': 0,
                                'market_heat': 0,
                                'activity_level': '0%',
                                'limit_up_count': 0,
                                'limit_down_count': 0
                            }
                        else:
                            up_count = sentiment_dict.get('上涨', 0)
                            down_count = sentiment_dict.get('下跌', 0)
                            limit_up_count = sentiment_dict.get('涨停', 0)
                            limit_down_count = sentiment_dict.get('跌停', 0)
                            flat_count = sentiment_dict.get('平盘', 0)
                            activity_level = sentiment_dict.get('活跃度', '0%')
                            
                            total_count = up_count + down_count + flat_count
                            up_down_ratio = round(up_count / down_count, 2) if down_count > 0 else 0
                            market_heat = round(up_count / total_count * 100, 2) if total_count > 0 else 0
                            
                            result = {
                                'up_count': up_count,
                                'down_count': down_count,
                                'flat_count': flat_count,
                                'total_count': total_count,
                                'up_down_ratio': up_down_ratio,
                                'market_heat': market_heat,
                                'activity_level': activity_level,
                                'limit_up_count': limit_up_count,
                                'limit_down_count': limit_down_count
                            }
                            logger.debug(f"[数据获取] 解析市场情绪DataFrame成功")
                else:
                    try:
                        sentiment_dict = dict(market_sentiment)
                        up_count = sentiment_dict.get('上涨', 0)
                        down_count = sentiment_dict.get('下跌', 0)
                        limit_up_count = sentiment_dict.get('涨停', 0)
                        limit_down_count = sentiment_dict.get('跌停', 0)
                        flat_count = sentiment_dict.get('平盘', 0)
                        activity_level = sentiment_dict.get('活跃度', '0%')
                        
                        total_count = up_count + down_count + flat_count
                        up_down_ratio = round(up_count / down_count, 2) if down_count > 0 else 0
                        market_heat = round(up_count / total_count * 100, 2) if total_count > 0 else 0
                        
                        result = {
                            'up_count': up_count,
                            'down_count': down_count,
                            'flat_count': flat_count,
                            'total_count': total_count,
                            'up_down_ratio': up_down_ratio,
                            'market_heat': market_heat,
                            'activity_level': activity_level,
                            'limit_up_count': limit_up_count,
                            'limit_down_count': limit_down_count
                        }
                        logger.debug(f"[数据获取] 解析市场情绪字典成功")
                    except Exception as e:
                        logger.error(f"[数据获取] 解析市场情绪数据失败: 错误: {str(e)}")
                        # 返回默认结果
                        result = {
                            'up_count': 0,
                            'down_count': 0,
                            'flat_count': 0,
                            'total_count': 0,
                            'up_down_ratio': 0,
                            'market_heat': 0,
                            'activity_level': '0%',
                            'limit_up_count': 0,
                            'limit_down_count': 0
                        }
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取市场情绪数据失败 (尝试{max_retries}次): 错误: {str(e)}")
                    return {}
                logger.warning(f"[数据获取] 获取市场情绪数据失败，重试中 (尝试{attempt+1}/{max_retries}): 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                retry_delay *= 1.5
                continue
            
            if self.cache:
                self.cache.set('market_sentiment', {}, result)
                logger.info(f"[数据缓存] 市场情绪数据已缓存")
            
            return result
    
    @performance_monitor
    def get_news_data(self, stock_code: str) -> Dict[str, Any]:
        """获取股票新闻数据"""
        if self.cache:
            cached_data = self.cache.get('news_data', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取新闻数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取新闻数据: {stock_code}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                # 使用akshare获取新闻数据
                news_data = ak.stock_news_em(symbol=stock_code)
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取新闻数据超时")
                
                if news_data is None or not isinstance(news_data, pd.DataFrame) or news_data.empty:
                    logger.info(f"[数据获取] 新闻数据为空: {stock_code}")
                    result = {
                        'news_count': 0,
                        'news_list': [],
                        'sentiment': '中性',
                        'keywords': []
                    }
                else:
                    news_list = []
                    for _, row in news_data.iterrows():
                        news_item = {
                            'title': row.get('title', ''),
                            'time': row.get('datetime', ''),
                            'source': row.get('source', ''),
                            'content': row.get('content', '')[:100] + '...' if row.get('content') else ''
                        }
                        news_list.append(news_item)
                    
                    # 简单的情绪判断（实际应用中应使用NLP）
                    positive_keywords = ['上涨', '利好', '增长', '突破', '创新高', '盈利', '涨停']
                    negative_keywords = ['下跌', '利空', '下降', '跌破', '创新低', '亏损', '跌停']
                    
                    positive_count = 0
                    negative_count = 0
                    keywords = []
                    
                    for news in news_list:
                        title = news.get('title', '')
                        content = news.get('content', '')
                        text = title + ' ' + content
                        
                        # 提取关键词
                        for kw in positive_keywords + negative_keywords:
                            if kw in text and kw not in keywords:
                                keywords.append(kw)
                        
                        # 统计情绪
                        for kw in positive_keywords:
                            if kw in text:
                                positive_count += 1
                                break
                        for kw in negative_keywords:
                            if kw in text:
                                negative_count += 1
                                break
                    
                    if positive_count > negative_count:
                        sentiment = '正面'
                    elif negative_count > positive_count:
                        sentiment = '负面'
                    else:
                        sentiment = '中性'
                    
                    result = {
                        'news_count': len(news_list),
                        'news_list': news_list,
                        'sentiment': sentiment,
                        'keywords': keywords[:5]  # 最多显示5个关键词
                    }
                    logger.debug(f"[数据获取] 解析新闻数据成功: {stock_code}")
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取新闻数据失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    # 返回默认结果
                    result = {
                        'news_count': 0,
                        'news_list': [],
                        'sentiment': '中性',
                        'keywords': []
                    }
                else:
                    logger.warning(f"[数据获取] 获取新闻数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                    time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                    retry_delay *= 1.5
                    continue
            
            if self.cache:
                self.cache.set('news_data', {'stock_code': stock_code}, result, ttl=3600)  # 新闻数据缓存1小时
                logger.info(f"[数据缓存] 新闻数据已缓存: {stock_code}")
            
            return result
    
    @performance_monitor
    def get_research_reports(self, stock_code: str) -> Dict[str, Any]:
        """获取股票研报数据"""
        if self.cache:
            cached_data = self.cache.get('research_reports', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取研报数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取研报数据: {stock_code}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                # 使用akshare获取研报数据（兼容处理：如果函数不存在则返回空数据）
                research_data = None
                try:
                    research_data = ak.stock_research_report_cninfo(symbol=stock_code, limit=5)
                except AttributeError:
                    # 如果函数不存在，直接返回空数据
                    logger.warning(f"[数据获取] 研报数据获取函数不存在，返回空数据: {stock_code}")
                    research_data = pd.DataFrame()
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取研报数据超时")
                
                if research_data is None or not isinstance(research_data, pd.DataFrame) or research_data.empty:
                    logger.info(f"[数据获取] 研报数据为空: {stock_code}")
                    result = {
                        'report_count': 0,
                        'reports': [],
                        'view': '中性',
                        'target_prices': []
                    }
                else:
                    reports = []
                    target_prices = []
                    
                    for _, row in research_data.iterrows():
                        report = {
                            'title': row.get('title', ''),
                            'institute': row.get('research_institute', ''),
                            'analyst': row.get('analyst', ''),
                            'date': row.get('publish_date', ''),
                            'rating': row.get('rating', ''),
                            'target_price': row.get('target_price', '')
                        }
                        reports.append(report)
                        
                        if report['target_price'] and report['target_price'] != '-':
                            try:
                                target_price = float(report['target_price'])
                                target_prices.append(target_price)
                            except:
                                pass
                    
                    # 统计研报观点
                    buy_ratings = ['买入', '强烈推荐', '推荐', '增持']
                    sell_ratings = ['卖出', '减持', '中性']
                    
                    buy_count = 0
                    sell_count = 0
                    
                    for report in reports:
                        rating = report['rating']
                        if rating in buy_ratings:
                            buy_count += 1
                        elif rating in sell_ratings:
                            sell_count += 1
                    
                    if buy_count > sell_count:
                        view = '看多'
                    elif sell_count > buy_count:
                        view = '看空'
                    else:
                        view = '中性'
                    
                    result = {
                        'report_count': len(reports),
                        'reports': reports,
                        'view': view,
                        'target_prices': target_prices
                    }
                    logger.debug(f"[数据获取] 解析研报数据成功: {stock_code}")
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取研报数据失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    # 返回默认结果
                    result = {
                        'report_count': 0,
                        'reports': [],
                        'view': '中性',
                        'target_prices': []
                    }
                else:
                    logger.warning(f"[数据获取] 获取研报数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                    time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                    retry_delay *= 1.5
                    continue
            
            if self.cache:
                self.cache.set('research_reports', {'stock_code': stock_code}, result, ttl=86400)  # 研报数据缓存1天
                logger.info(f"[数据缓存] 研报数据已缓存: {stock_code}")
            
            return result
    
    @performance_monitor
    def get_social_media_sentiment(self, stock_code: str) -> Dict[str, Any]:
        """获取社交媒体舆情数据"""
        if self.cache:
            cached_data = self.cache.get('social_media_sentiment', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取社交媒体舆情数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取社交媒体舆情数据: {stock_code}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                # 模拟社交媒体舆情数据（实际应用中应接入社交媒体API）
                # 这里使用akshare的市场情绪数据作为替代
                market_sentiment = self.get_market_sentiment()
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取社交媒体舆情数据超时")
                
                # 根据市场情绪生成模拟的社交媒体数据
                market_heat = market_sentiment.get('market_heat', 50)
                
                if market_heat > 70:
                    heat_level = '高'
                elif market_heat < 30:
                    heat_level = '低'
                else:
                    heat_level = '中'
                
                # 简单的情绪判断
                up_count = market_sentiment.get('up_count', 0)
                down_count = market_sentiment.get('down_count', 1)
                sentiment_score = up_count / down_count if down_count > 0 else 0
                
                if sentiment_score > 1.5:
                    sentiment = '正面'
                elif sentiment_score < 0.7:
                    sentiment = '负面'
                else:
                    sentiment = '中性'
                
                result = {
                    'heat_level': heat_level,
                    'sentiment': sentiment,
                    'mention_count': int(market_heat * 10),  # 模拟提及次数
                    'discussion_count': int(market_heat * 5),  # 模拟讨论次数
                    'sentiment_score': round(sentiment_score, 2),
                    'hot_topics': ['市场情绪', '资金流向', '技术形态', '基本面', '政策影响']  # 模拟热门话题
                }
                logger.debug(f"[数据获取] 解析社交媒体舆情数据成功: {stock_code}")
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取社交媒体舆情数据失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    # 返回默认结果
                    result = {
                        'heat_level': '中',
                        'sentiment': '中性',
                        'mention_count': 0,
                        'discussion_count': 0,
                        'sentiment_score': 0.0,
                        'hot_topics': []
                    }
                else:
                    logger.warning(f"[数据获取] 获取社交媒体舆情数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                    time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                    retry_delay *= 1.5
                    continue
            
            if self.cache:
                self.cache.set('social_media_sentiment', {'stock_code': stock_code}, result, ttl=1800)  # 社交媒体数据缓存30分钟
                logger.info(f"[数据缓存] 社交媒体舆情数据已缓存: {stock_code}")
            
            return result
    
    @performance_monitor
    def get_public_opinion(self, stock_code: str) -> Dict[str, Any]:
        """获取综合舆情数据"""
        news_data = self.get_news_data(stock_code)
        research_reports = self.get_research_reports(stock_code)
        social_media = self.get_social_media_sentiment(stock_code)
        
        # 综合舆情评级
        sentiment_weights = {
            'news': 0.4,
            'research': 0.4,
            'social': 0.2
        }
        
        sentiment_map = {
            '正面': 1,
            '中性': 0,
            '负面': -1
        }
        
        news_score = sentiment_map.get(news_data.get('sentiment', '中性'), 0)
        research_score = sentiment_map.get(research_reports.get('view', '中性'), 0)
        social_score = sentiment_map.get(social_media.get('sentiment', '中性'), 0)
        
        total_score = (news_score * sentiment_weights['news'] + 
                     research_score * sentiment_weights['research'] + 
                     social_score * sentiment_weights['social'])
        
        if total_score > 0.5:
            overall_sentiment = '正面'
        elif total_score < -0.5:
            overall_sentiment = '负面'
        else:
            overall_sentiment = '中性'
        
        return {
            'news_data': news_data,
            'research_reports': research_reports,
            'social_media': social_media,
            'overall_sentiment': overall_sentiment,
            'sentiment_score': round(total_score, 2)
        }
    
    @performance_monitor
    def get_industry_comparison(self, stock_code: str) -> Dict[str, Any]:
        """获取行业比较数据"""
        if self.cache:
            cached_data = self.cache.get('industry_comparison', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取行业比较数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取行业比较数据: {stock_code}")
        
        # 由于akshare的限制，这里使用简化的行业比较数据
        # 实际应用中应获取真实的行业数据
        result = {
            'industry_pe': '25.0',  # 模拟行业平均PE
            'industry_pb': '3.5',   # 模拟行业平均PB
            'industry_roe': '15.0',  # 模拟行业平均ROE
            'industry_growth_rate': '10.0'  # 模拟行业平均增长率
        }
        
        if self.cache:
            self.cache.set('industry_comparison', {'stock_code': stock_code}, result, ttl=86400)  # 行业数据缓存1天
        
        return result
    
    def get_valuation_data(self, stock_code: str) -> Dict[str, Any]:
        """获取估值相关数据"""
        if self.cache:
            cached_data = self.cache.get('valuation_data', {'stock_code': stock_code})
            if cached_data:
                logger.info(f"[数据缓存] 获取估值数据缓存命中: {stock_code}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取估值数据: {stock_code}")
        
        try:
            # 获取股票实时数据
            stock_info = self.get_stock_info(stock_code)
            current_price = stock_info.get('current_price', 0)
            pe_ratio = stock_info.get('pe_ratio', 0)
            pb_ratio = stock_info.get('pb_ratio', 0)
            
            # 获取财务数据
            financial_data = self.get_financial_data(stock_code)
            eps = financial_data.get('eps', 0)
            book_value_per_share = financial_data.get('book_value_per_share', 0)
            
            # 计算PEG（市盈率相对盈利增长比率）
            profit_growth = financial_data.get('profit_growth', 0)
            try:
                profit_growth = float(profit_growth) if profit_growth else 0
                peg = pe_ratio / profit_growth if profit_growth != 0 else 0
            except:
                peg = 0
            
            # 计算股息率（模拟数据）
            dividend_yield = 1.5  # 模拟股息率
            
            result = {
                'current_price': current_price,
                'pe_ratio': pe_ratio,
                'pb_ratio': pb_ratio,
                'eps': eps,
                'book_value_per_share': book_value_per_share,
                'peg_ratio': round(peg, 2),
                'dividend_yield': dividend_yield
            }
        except Exception as e:
            logger.error(f"[数据获取] 获取估值数据失败: {stock_code}, 错误: {str(e)}")
            result = {
                'current_price': 0,
                'pe_ratio': 0,
                'pb_ratio': 0,
                'eps': 0,
                'book_value_per_share': 0,
                'peg_ratio': 0,
                'dividend_yield': 0
            }
        
        if self.cache:
            self.cache.set('valuation_data', {'stock_code': stock_code}, result, ttl=3600)  # 估值数据缓存1小时
        
        return result
    
    def get_comprehensive_data(self, stock_code: str) -> Dict[str, Any]:
        stock_info = self.get_stock_info(stock_code)
        kline_data = self.get_kline_data(stock_code)
        financial_data = self.get_financial_data(stock_code)
        fund_flow = self.get_fund_flow(stock_code)
        market_sentiment = self.get_market_sentiment()
        public_opinion = self.get_public_opinion(stock_code)
        industry_comparison = self.get_industry_comparison(stock_code)
        valuation_data = self.get_valuation_data(stock_code)
        
        kline_records = []
        try:
            if not kline_data.empty:
                kline_records = kline_data.to_dict('records')
        except Exception as e:
            kline_records = []
        
        return {
            'stock_info': stock_info,
            'kline_data': kline_records,
            'financial_data': financial_data,
            'fund_flow': fund_flow,
            'market_sentiment': market_sentiment,
            'public_opinion': public_opinion,
            'industry_comparison': industry_comparison,
            'valuation_data': valuation_data
        }
    
    @performance_monitor
    def get_sector_list(self) -> Dict[str, Any]:
        """获取板块列表"""
        if self.cache:
            cached_data = self.cache.get('sector_list', {})
            if cached_data:
                logger.info(f"[数据缓存] 获取板块列表缓存命中")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取板块列表")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                # 使用akshare获取板块列表
                sector_df = ak.stock_board_industry_name_em()
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取板块列表超时")
                
                if sector_df is None or not isinstance(sector_df, pd.DataFrame) or sector_df.empty:
                    logger.info(f"[数据获取] 板块列表数据为空")
                    result = {}
                else:
                    sectors = []
                    for _, row in sector_df.iterrows():
                        sector_item = {
                            'sector_name': row.get('板块名称', ''),
                            'sector_code': row.get('板块代码', '')
                        }
                        sectors.append(sector_item)
                    
                    result = {
                        'sectors': sectors,
                        'count': len(sectors)
                    }
                    logger.debug(f"[数据获取] 解析板块列表成功")
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取板块列表失败 (尝试{max_retries}次): 错误: {str(e)}")
                    return {}
                logger.warning(f"[数据获取] 获取板块列表失败，重试中 (尝试{attempt+1}/{max_retries}): 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))
                retry_delay *= 1.5
                continue
        
        if self.cache:
            self.cache.set('sector_list', {}, result, ttl=86400)  # 板块列表缓存1天
        
        return result
    
    def validate_sector(self, sector_name: str) -> Dict[str, Any]:
        """验证板块是否存在"""
        sector_list = self.get_sector_list()
        sectors = sector_list.get('sectors', [])
        
        # 检查板块是否存在
        sector_exists = any(sector.get('sector_name') == sector_name for sector in sectors)
        
        return {
            'exists': sector_exists,
            'sector_name': sector_name,
            'supported_sectors': sectors
        }
    
    def get_sectors_by_category(self) -> Dict[str, Any]:
        """获取分类的板块列表"""
        if self.cache:
            cached_data = self.cache.get('sectors_by_category', {})
            if cached_data:
                logger.info(f"[数据缓存] 获取分类板块列表缓存命中")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取分类板块列表")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                # 使用akshare获取板块列表
                sector_df = ak.stock_board_industry_name_em()
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取板块列表超时")
                
                if sector_df is None or not isinstance(sector_df, pd.DataFrame) or sector_df.empty:
                    logger.info(f"[数据获取] 板块列表数据为空")
                    result = {}
                else:
                    # 定义板块分类规则
                    category_rules = {
                        '半导体': ['半导体', '芯片', '集成电路', 'IC'],
                        '新能源': ['新能源', '光伏', '风电', '储能', '锂电池', '氢能源'],
                        '医药': ['医药', '医疗', '生物', '疫苗', '创新药'],
                        '消费': ['消费', '食品', '饮料', '白酒', '家电', '零售'],
                        '金融': ['银行', '证券', '保险', '金融', '券商', '基金'],
                        '科技': ['科技', '软件', '互联网', '通信', '5G', 'AI', '人工智能'],
                        '制造业': ['制造', '工业', '机械', '设备'],
                        '材料': ['材料', '化工', '钢铁', '有色', '建材'],
                        '地产': ['地产', '房地产', '建筑', '物业'],
                        '交通运输': ['交通', '运输', '物流', '航空', '港口']
                    }
                    
                    # 未分类板块
                    uncategorized = []
                    
                    # 按分类组织板块
                    categories = {category: [] for category in category_rules.keys()}
                    
                    for _, row in sector_df.iterrows():
                        sector_name = row.get('板块名称', '')
                        sector_code = row.get('板块代码', '')
                        sector_item = {
                            'sector_name': sector_name,
                            'sector_code': sector_code
                        }
                        
                        # 匹配分类
                        matched = False
                        for category, keywords in category_rules.items():
                            for keyword in keywords:
                                if keyword in sector_name:
                                    categories[category].append(sector_item)
                                    matched = True
                                    break
                            if matched:
                                break
                        
                        if not matched:
                            uncategorized.append(sector_item)
                    
                    # 添加未分类板块
                    if uncategorized:
                        categories['其他'] = uncategorized
                    
                    # 计算每个分类的板块数量
                    category_counts = {category: len(sectors) for category, sectors in categories.items()}
                    
                    result = {
                        'categories': categories,
                        'category_counts': category_counts,
                        'total_count': len(sector_df)
                    }
                    logger.debug(f"[数据获取] 解析分类板块列表成功")
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取分类板块列表失败 (尝试{max_retries}次): 错误: {str(e)}")
                    return {}
                logger.warning(f"[数据获取] 获取分类板块列表失败，重试中 (尝试{attempt+1}/{max_retries}): 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))
                retry_delay *= 1.5
                continue
        
        if self.cache:
            self.cache.set('sectors_by_category', {}, result, ttl=86400)  # 分类板块列表缓存1天
        
        return result
    
    @performance_monitor
    def get_sector_components(self, sector_name: str) -> Dict[str, Any]:
        """获取板块成分股"""
        if self.cache:
            cached_data = self.cache.get('sector_components', {'sector_name': sector_name})
            # 只有当缓存的数据有效（成分股数量>0）时，才返回缓存数据
            if cached_data and cached_data.get('count', 0) > 0:
                logger.info(f"[数据缓存] 获取板块成分股缓存命中: {sector_name}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取板块成分股: {sector_name}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                # 使用akshare获取板块成分股 - 添加超时控制
                components_df = run_with_timeout(
                    lambda: ak.stock_board_industry_cons_em(symbol=sector_name),
                    timeout=15.0,
                    default=None
                )
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取板块成分股超时")
                
                if components_df is None or not isinstance(components_df, pd.DataFrame) or components_df.empty:
                    logger.info(f"[数据获取] 板块成分股数据为空: {sector_name}")
                    # 不缓存空数据
                    return {
                        'sector_name': sector_name,
                        'components': [],
                        'count': 0
                    }
                else:
                    components = []
                    for _, row in components_df.iterrows():
                        component_item = {
                            'stock_code': row.get('代码', ''),
                            'stock_name': row.get('名称', '')
                        }
                        components.append(component_item)
                    
                    result = {
                        'sector_name': sector_name,
                        'components': components,
                        'count': len(components)
                    }
                    logger.debug(f"[数据获取] 解析板块成分股成功: {sector_name}")
                
                if self.cache:
                    self.cache.set('sector_components', {'sector_name': sector_name}, result, ttl=3600)  # 板块成分股缓存1小时
                
                return result
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取板块成分股失败 (尝试{max_retries}次): {sector_name}, 错误: {str(e)}")
                    # 不缓存失败数据
                    return {
                        'sector_name': sector_name,
                        'components': [],
                        'count': 0
                    }
                logger.warning(f"[数据获取] 获取板块成分股失败，重试中 (尝试{attempt+1}/{max_retries}): {sector_name}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))
                retry_delay *= 1.5
                continue
        
        # 兜底返回（理论上不会执行到这里）
        return {
            'sector_name': sector_name,
            'components': [],
            'count': 0
        }
    
    @performance_monitor
    def get_sector_data(self, sector_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """获取板块综合数据"""
        if self.cache and use_cache:
            cached_data = self.cache.get('sector_data', {'sector_name': sector_name})
            if cached_data:
                logger.info(f"[数据缓存] 获取板块数据缓存命中: {sector_name}")
                return cached_data
        
        logger.info(f"[数据获取] 开始获取板块数据: {sector_name}")
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                # 获取板块成分股
                components_data = self.get_sector_components(sector_name)
                components = components_data.get('components', [])
                component_count = components_data.get('count', 0)
                
                # 构建板块基本信息
                sector_info = {
                    'sector_name': sector_name,
                    'timestamp': datetime.now().isoformat(),
                    'component_count': component_count
                }
                
                # 板块表现数据
                performance = {
                    'today_change': '',
                    '5d_change': '',
                    '30d_change': '',
                    'vs_market': ''
                }
                
                # 板块内个股表现
                component_performance = {
                    'top_gainers': [],
                    'top_losers': [],
                    'avg_change': '',
                    'up_down_ratio': ''
                }
                
                # 资金流向数据
                fund_flow = {
                    'sector_net_inflow': '',
                    'main_net_inflow': '',
                    'north_net_inflow': '',
                    'heat_level': ''
                }
                
                # 估值数据
                valuation = {
                    'avg_pe': '',
                    'avg_pb': '',
                    'pe_history_percentile': '',
                    'vs_market_valuation': ''
                }
                
                # 板块轮动数据
                rotation = {
                    'current_style': '',
                    'position_in_rotation': '',
                    'rotation_signal': ''
                }
                
                # 政策与行业趋势
                policy_trends = {
                    'latest_policy': '',
                    'industry_trend': '',
                    'positive_factors': [],
                    'negative_factors': []
                }
                
                # 获取板块实时行情（传入板块名称作为参数）- 添加超时控制
                logger.info(f"[数据获取] 开始获取板块实时行情: {sector_name}")
                sector_spot_df = run_with_timeout(
                    lambda: ak.stock_board_industry_spot_em(symbol=sector_name),
                    timeout=15.0,
                    default=None
                )
                logger.info(f"[数据获取] 板块实时行情获取完成: {sector_name}, 结果: {sector_spot_df is not None and not sector_spot_df.empty}")
                if sector_spot_df is not None and not sector_spot_df.empty:
                    # 转换为字典格式以便于访问
                    spot_dict = dict(zip(sector_spot_df['item'], sector_spot_df['value']))
                    
                    # 填充板块表现数据
                    performance['today_change'] = f"{spot_dict.get('涨跌幅', '')}%" if spot_dict.get('涨跌幅') is not None else ''
                    
                    # 填充资金流向数据
                    fund_flow['sector_net_inflow'] = spot_dict.get('成交额', '')
                    fund_flow['heat_level'] = spot_dict.get('换手率', '')
                
                # 获取板块列表数据，用于获取总市值等信息 - 添加超时控制
                try:
                    logger.info(f"[数据获取] 开始获取板块列表数据")
                    sector_list_df = run_with_timeout(
                        lambda: ak.stock_board_industry_name_em(),
                        timeout=15.0,
                        default=None
                    )
                    logger.info(f"[数据获取] 板块列表数据获取完成, 结果: {sector_list_df is not None and not sector_list_df.empty}")
                    if sector_list_df is not None and not sector_list_df.empty:
                        # 查找当前板块
                        sector_row = sector_list_df[sector_list_df['板块名称'] == sector_name]
                        if not sector_row.empty:
                            sector_row = sector_row.iloc[0]
                            sector_info['total_market_cap'] = sector_row.get('总市值', '')
                except Exception as e:
                    logger.warning(f"[数据获取] 获取板块列表数据失败: {str(e)}")
                
                # 获取板块历史行情数据，用于计算5日和30日涨跌幅、技术指标 - 添加超时控制
                try:
                    logger.info(f"[数据获取] 开始获取板块历史行情数据: {sector_name}")
                    sector_hist_df = run_with_timeout(
                        lambda: ak.stock_board_industry_hist_em(symbol=sector_name),
                        timeout=15.0,
                        default=None
                    )
                    logger.info(f"[数据获取] 板块历史行情数据获取完成: {sector_name}, 结果: {sector_hist_df is not None and not sector_hist_df.empty}")
                    if sector_hist_df is not None and not sector_hist_df.empty:
                        # 计算5日和30日涨跌幅
                        if len(sector_hist_df) >= 5:
                            start_price_5d = sector_hist_df.iloc[-5]['收盘']
                            end_price_5d = sector_hist_df.iloc[-1]['收盘']
                            change_5d = ((end_price_5d - start_price_5d) / start_price_5d) * 100
                            performance['5d_change'] = f"{change_5d:.2f}%"
                        
                        if len(sector_hist_df) >= 30:
                            start_price_30d = sector_hist_df.iloc[-30]['收盘']
                            end_price_30d = sector_hist_df.iloc[-1]['收盘']
                            change_30d = ((end_price_30d - start_price_30d) / start_price_30d) * 100
                            performance['30d_change'] = f"{change_30d:.2f}%"
                        
                        # 计算技术指标
                        if len(sector_hist_df) >= 20:
                            closes = sector_hist_df['收盘'].values
                            
                            # 计算MA5、MA10、MA20
                            ma5 = closes[-5:].mean()
                            ma10 = closes[-10:].mean()
                            ma20 = closes[-20:].mean()
                            current_price = closes[-1]
                            
                            # 判断趋势
                            if current_price > ma5 > ma10 > ma20:
                                trend = '强势上涨'
                            elif current_price > ma5 and current_price < ma20:
                                trend = '震荡'
                            elif current_price < ma5 < ma10 < ma20:
                                trend = '弱势下跌'
                            else:
                                trend = '震荡'
                            
                            rotation['current_style'] = trend
                            rotation['position_in_rotation'] = '上升期' if current_price > ma20 else '下跌期'
                            rotation['rotation_signal'] = f"当前价格{current_price:.2f}，MA5:{ma5:.2f}，MA10:{ma10:.2f}，MA20:{ma20:.2f}"
                        
                        # 计算估值历史分位（使用成分股的平均PE数据）
                        if len(sector_hist_df) >= 60 and valuation.get('avg_pe'):
                            try:
                                current_pe = float(valuation['avg_pe'])
                                if current_pe > 0:
                                    # 假设历史PE在10-50之间波动（简化处理）
                                    pe_percentile = min(100, max(0, ((current_pe - 10) / 40) * 100))
                                    valuation['pe_history_percentile'] = f"{pe_percentile:.1f}%"
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"[数据获取] 获取板块历史行情失败: {str(e)}")
                
                # 获取与大盘对比数据 - 添加超时控制
                try:
                    # 获取上证指数数据
                    logger.info(f"[数据获取] 开始获取上证指数数据")
                    index_hist_df = run_with_timeout(
                        lambda: ak.stock_zh_index_daily(symbol="sh000001"),
                        timeout=10.0,
                        default=None
                    )
                    logger.info(f"[数据获取] 上证指数数据获取完成, 结果: {index_hist_df is not None and not index_hist_df.empty}")
                    
                    if index_hist_df is not None and not index_hist_df.empty and len(index_hist_df) >= 30:
                        index_change_30d = ((index_hist_df.iloc[-1]['close'] - index_hist_df.iloc[-30]['close']) / index_hist_df.iloc[-30]['close']) * 100
                        
                        # 对比板块与大盘
                        sector_change_30d_str = performance.get('30d_change', '0%')
                        sector_change_30d = float(sector_change_30d_str.replace('%', '')) if sector_change_30d_str else 0
                        
                        if sector_change_30d > index_change_30d + 2:
                            performance['vs_market'] = '强于大盘'
                        elif sector_change_30d < index_change_30d - 2:
                            performance['vs_market'] = '弱于大盘'
                        else:
                            performance['vs_market'] = '持平'
                        
                        # 估值对比
                        if valuation.get('avg_pe'):
                            sector_pe = float(valuation['avg_pe']) if isinstance(valuation['avg_pe'], (int, float)) else 0
                            # 上证指数平均PE约13
                            if sector_pe < 13 * 0.8:
                                valuation['vs_market_valuation'] = '低估'
                            elif sector_pe > 13 * 1.2:
                                valuation['vs_market_valuation'] = '高估'
                            else:
                                valuation['vs_market_valuation'] = '合理'
                    else:
                        logger.warning(f"[数据获取] 上证指数数据不足30条，无法进行对比分析")
                except Exception as e:
                    logger.warning(f"[数据获取] 获取大盘对比数据失败: {str(e)}")
                
                # 添加政策与行业趋势数据（基于板块名称的简单分析）
                try:
                    sector_lower = sector_name.lower()
                    
                    # 根据板块名称推断行业趋势
                    if any(keyword in sector_lower for keyword in ['新能源', '光伏', '风电', '储能']):
                        policy_trends['industry_trend'] = '新能源行业受国家政策大力支持，碳中和目标驱动长期发展'
                        policy_trends['latest_policy'] = '国家发改委发布新能源发展规划，加大光伏、风电装机容量'
                        policy_trends['positive_factors'] = ['政策支持', '碳中和目标', '技术进步', '成本下降']
                        policy_trends['negative_factors'] = ['产能过剩风险', '补贴退坡', '原材料价格波动']
                    elif any(keyword in sector_lower for keyword in ['半导体', '芯片', '集成电路']):
                        policy_trends['industry_trend'] = '半导体行业国产化替代加速，政策扶持力度加大'
                        policy_trends['latest_policy'] = '国家大基金三期投资半导体产业，支持关键技术突破'
                        policy_trends['positive_factors'] = ['国产化替代', '政策扶持', '市场需求增长', '技术突破']
                        policy_trends['negative_factors'] = ['技术壁垒高', '国际竞争激烈', '研发投入大']
                    elif any(keyword in sector_lower for keyword in ['医药', '生物', '医疗']):
                        policy_trends['industry_trend'] = '医药行业受人口老龄化驱动，创新药政策利好'
                        policy_trends['latest_policy'] = '医保目录调整加速，创新药审批流程优化'
                        policy_trends['positive_factors'] = ['人口老龄化', '医疗需求增长', '创新药政策', '国产替代']
                        policy_trends['negative_factors'] = ['集采降价', '研发风险', '监管趋严']
                    elif any(keyword in sector_lower for keyword in ['汽车', '新能源车', '智能汽车']):
                        policy_trends['industry_trend'] = '新能源汽车渗透率持续提升，智能化成为新趋势'
                        policy_trends['latest_policy'] = '新能源汽车购置补贴延续至2027年，智能网联汽车发展提速'
                        policy_trends['positive_factors'] = ['政策补贴', '技术进步', '消费升级', '出口增长']
                        policy_trends['negative_factors'] = ['价格战', '补贴退坡', '竞争激烈']
                    elif any(keyword in sector_lower for keyword in ['人工智能', 'AI', '云计算', '大数据']):
                        policy_trends['industry_trend'] = 'AI技术快速发展，应用场景不断拓展'
                        policy_trends['latest_policy'] = '国家发布人工智能发展规划，支持AI基础设施建设'
                        policy_trends['positive_factors'] = ['技术突破', '应用场景丰富', '政策支持', '市场需求大']
                        policy_trends['negative_factors'] = ['监管风险', '技术不确定性', '竞争激烈']
                    else:
                        policy_trends['industry_trend'] = '行业处于稳定发展阶段，关注基本面和估值水平'
                        policy_trends['latest_policy'] = '保持稳健货币政策，支持实体经济发展'
                        policy_trends['positive_factors'] = ['经济复苏', '政策支持', '市场需求']
                        policy_trends['negative_factors'] = ['宏观经济风险', '行业竞争', '成本压力']
                except Exception as e:
                    logger.warning(f"[数据获取] 生成政策趋势数据失败: {str(e)}")
                
                # 获取板块成分股的实时行情，计算板块内个股表现
                if components:
                    try:
                        # 使用板块成分股API获取实时行情（包含涨跌幅等信息）
                        logger.info(f"[数据获取] 开始获取板块成分股实时行情: {sector_name}")
                        logger.info(f"[数据获取] 成分股数量: {len(components)}")
                        
                        component_quotes_df = run_with_timeout(
                            lambda: ak.stock_board_industry_cons_em(symbol=sector_name),
                            timeout=15.0,
                            default=None
                        )
                        
                        logger.info(f"[数据获取] 板块成分股实时行情获取完成: {sector_name}")
                        logger.info(f"[数据获取] component_quotes_df is None: {component_quotes_df is None}")
                        if component_quotes_df is not None:
                            logger.info(f"[数据获取] component_quotes_df.empty: {component_quotes_df.empty}")
                            logger.info(f"[数据获取] component_quotes_df shape: {component_quotes_df.shape if hasattr(component_quotes_df, 'shape') else 'N/A'}")
                        
                        if component_quotes_df is not None and not component_quotes_df.empty:
                            logger.info(f"[数据获取] 开始计算板块成分股指标")
                            # 计算平均涨跌幅
                            avg_change = component_quotes_df['涨跌幅'].mean()
                            component_performance['avg_change'] = f"{avg_change:.2f}%" if not pd.isna(avg_change) else ''
                            logger.info(f"[数据获取] 平均涨跌幅: {component_performance['avg_change']}")
                            
                            # 计算涨跌比
                            up_count = len(component_quotes_df[component_quotes_df['涨跌幅'] > 0])
                            down_count = len(component_quotes_df[component_quotes_df['涨跌幅'] < 0])
                            component_performance['up_down_ratio'] = f"{up_count}:{down_count}"
                            logger.info(f"[数据获取] 涨跌比: {component_performance['up_down_ratio']}")
                            
                            # 获取领涨领跌个股（各取前3名）
                            sorted_by_change = component_quotes_df.sort_values('涨跌幅', ascending=False)
                            top_gainers = sorted_by_change.head(3)
                            top_losers = sorted_by_change.tail(3)
                            
                            # 构建领涨个股列表
                            component_performance['top_gainers'] = [
                                (row['名称'], f"{row['涨跌幅']:.2f}%") 
                                for _, row in top_gainers.iterrows()
                            ]
                            logger.info(f"[数据获取] 领涨个股: {component_performance['top_gainers']}")
                            
                            # 构建领跌个股列表
                            component_performance['top_losers'] = [
                                (row['名称'], f"{row['涨跌幅']:.2f}%") 
                                for _, row in top_losers.iterrows()
                            ]
                            logger.info(f"[数据获取] 领跌个股: {component_performance['top_losers']}")
                            
                            # 计算板块平均PE和PB
                            avg_pe = component_quotes_df['市盈率-动态'].mean()
                            avg_pb = component_quotes_df['市净率'].mean()
                            valuation['avg_pe'] = f"{avg_pe:.2f}" if not pd.isna(avg_pe) else ''
                            valuation['avg_pb'] = f"{avg_pb:.2f}" if not pd.isna(avg_pb) else ''
                            logger.info(f"[数据获取] 平均PE: {valuation['avg_pe']}, 平均PB: {valuation['avg_pb']}")
                        else:
                            logger.warning(f"[数据获取] 板块成分股数据为空或获取失败")
                    except Exception as e:
                        logger.warning(f"[数据获取] 获取板块成分股行情失败: {str(e)}")
                        import traceback
                        logger.warning(f"[数据获取] 堆栈跟踪: {traceback.format_exc()}")
                
                # 获取板块资金流向数据（使用try-except隔离，避免超时影响整体）- 添加超时控制
                try:
                    logger.info(f"[数据获取] 开始获取板块资金流向数据: {sector_name}")
                    fund_flow_data = run_with_timeout(
                        lambda: ak.stock_fund_flow_industry(),
                        timeout=15.0,
                        default=None
                    )
                    logger.info(f"[数据获取] 板块资金流向数据获取完成: {sector_name}, 结果: {fund_flow_data is not None}")
                    if fund_flow_data is not None and not fund_flow_data.empty:
                        sector_fund_flow = fund_flow_data[fund_flow_data['行业'] == sector_name]
                        if not sector_fund_flow.empty:
                            fund_flow_row = sector_fund_flow.iloc[0]
                            # 使用净额字段作为主力净流入（API返回的单位是亿元）
                            net_inflow = fund_flow_row.get('净额', 0)
                            if isinstance(net_inflow, (int, float)):
                                fund_flow['main_net_inflow'] = f"{net_inflow:.2f}亿元"
                            else:
                                fund_flow['main_net_inflow'] = str(net_inflow) if net_inflow else ''
                            
                            # 北向资金数据需要从其他API获取，这里暂时留空
                            fund_flow['north_net_inflow'] = '数据暂缺'
                            
                            # 计算资金热度（基于净流入金额）
                            if isinstance(net_inflow, (int, float)):
                                if net_inflow > 10:
                                    fund_flow['heat_level'] = '高'
                                elif net_inflow > 0:
                                    fund_flow['heat_level'] = '中'
                                else:
                                    fund_flow['heat_level'] = '低'
                            logger.info(f"[数据获取] 主力资金净流入: {fund_flow['main_net_inflow']}, 资金热度: {fund_flow['heat_level']}")
                except Exception as e:
                    logger.warning(f"[数据获取] 获取板块资金流向失败: {str(e)}")
                
                result = {
                    **sector_info,
                    'performance': performance,
                    'component_performance': component_performance,
                    'fund_flow': fund_flow,
                    'valuation': valuation,
                    'rotation': rotation,
                    'policy_trends': policy_trends
                }
                
                end_time = time.time()
                
                if end_time - start_time > GLOBAL_TIMEOUT:
                    raise Exception("获取板块数据超时")
                
                logger.debug(f"[数据获取] 解析板块数据成功: {sector_name}")
                
                if self.cache:
                    self.cache.set('sector_data', {'sector_name': sector_name}, result, ttl=3600)  # 板块数据缓存1小时
                
                return result
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取板块数据失败 (尝试{max_retries}次): {sector_name}, 错误: {str(e)}")
                    return {
                        'sector_name': sector_name,
                        'timestamp': datetime.now().isoformat(),
                        'component_count': 0,
                        'performance': {},
                        'component_performance': {},
                        'fund_flow': {},
                        'valuation': {},
                        'rotation': {},
                        'policy_trends': {}
                    }
                logger.warning(f"[数据获取] 获取板块数据失败，重试中 (尝试{attempt+1}/{max_retries}): {sector_name}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))
                retry_delay *= 1.5
                continue
        
        # 兜底返回（理论上不会执行到这里）
        return {
            'sector_name': sector_name,
            'timestamp': datetime.now().isoformat(),
            'component_count': 0,
            'performance': {},
            'component_performance': {},
            'fund_flow': {},
            'valuation': {},
            'rotation': {},
            'policy_trends': {}
        }
    
    @performance_monitor
    def search_stock(self, keyword: str) -> list[Dict[str, Any]]:
        """搜索股票代码和名称"""
        if not keyword or len(keyword.strip()) == 0:
            return []
        
        logger.info(f"[数据获取] 开始搜索股票: {keyword}")
        stock_list = self._get_stock_list_data()
        if stock_list is None or stock_list.empty:
            return []

        code_col = "code" if "code" in stock_list.columns else ("代码" if "代码" in stock_list.columns else None)
        name_col = "name" if "name" in stock_list.columns else ("名称" if "名称" in stock_list.columns else None)
        if code_col is None or name_col is None:
            return []

        kw = keyword.strip()
        try:
            filtered = stock_list[
                stock_list[code_col].astype(str).str.contains(kw, case=False, na=False)
                | stock_list[name_col].astype(str).str.contains(kw, case=False, na=False)
            ]
        except Exception:
            return []

        spot_df = self._peek_spot_cache()
        results: list[Dict[str, Any]] = []
        for _, row in filtered.head(10).iterrows():
            stock_code = str(row.get(code_col, "")).strip()
            stock_name = str(row.get(name_col, "")).strip()
            current_price = ""
            change_percent = ""
            if spot_df is not None and not spot_df.empty and "代码" in spot_df.columns:
                try:
                    spot_row = spot_df[spot_df["代码"] == stock_code]
                    if not spot_row.empty:
                        spot = spot_row.iloc[0]
                        current_price = spot.get("最新价", "")
                        change_percent = spot.get("涨跌幅", "")
                except Exception:
                    pass

            results.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "current_price": current_price,
                    "change_percent": change_percent,
                }
            )

        logger.info(f"[数据获取] 搜索股票成功，找到 {len(results)} 条结果")
        return results
