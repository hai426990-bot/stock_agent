import akshare as ak
import pandas as pd
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .data_cache import DataCache
from .logger import logger
from .performance_monitor import performance_monitor
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import re

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
        
        df = ak.stock_zh_a_spot_em()
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
                        'timestamp': datetime.now().isoformat()
                    }
                
                if self.cache:
                    self.cache.set('stock_info', {'stock_code': stock_code}, result)
                    logger.info(f"[数据缓存] 股票信息已缓存: {stock_code}")
                
                logger.info(f"[数据获取] 获取股票信息成功: {stock_code}, 耗时: {end_time - start_time:.2f}s")
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
            if cached_data:
                logger.info(f"[数据缓存] 获取K线数据缓存命中: {stock_code}, 周期: {period}, 数量: {count}")
                return pd.DataFrame(cached_data)
        
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
                    cache_df = result
                    if isinstance(cache_df, pd.DataFrame) and '日期' in cache_df.columns:
                        try:
                            cache_df = cache_df.copy()
                            cache_df['日期'] = cache_df['日期'].astype(str)
                        except Exception:
                            cache_df = result
                    self.cache.set('kline_data', {'stock_code': stock_code, 'period': period, 'count': count}, cache_df.to_dict('records'))
                    logger.info(f"[数据缓存] K线数据已缓存: {stock_code}, 周期: {period}, 数量: {count}")
                
                logger.info(f"[数据获取] 获取K线数据成功: {stock_code}, 周期: {period}, 数量: {count}, 耗时: {end_time - start_time:.2f}s")
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取K线数据失败 (尝试{max_retries}次): {stock_code}, 周期: {period}, 错误: {str(e)}")
                    raise Exception(f"获取K线数据失败: {str(e)}")
                logger.warning(f"[数据获取] 获取K线数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 周期: {period}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
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
                        'profit_growth': get_indicator_value('归属母公司净利润增长率')
                    }
                    logger.debug(f"[数据获取] 解析财务数据成功: {stock_code}")
            
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[数据获取] 获取财务数据失败 (尝试{max_retries}次): {stock_code}, 错误: {str(e)}")
                    return {}
                logger.warning(f"[数据获取] 获取财务数据失败，重试中 (尝试{attempt+1}/{max_retries}): {stock_code}, 错误: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                retry_delay *= 1.5
                continue
            
            if self.cache:
                self.cache.set('financial_data', {'stock_code': stock_code}, result)
                logger.info(f"[数据缓存] 财务数据已缓存: {stock_code}")
            
            logger.info(f"[数据获取] 获取财务数据成功: {stock_code}, 耗时: {end_time - start_time:.2f}s")
            return result
        
        return {}
    
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
            
            logger.info(f"[数据获取] 获取资金流向数据成功: {stock_code}, 耗时: {end_time - start_time:.2f}s")
            return result
        
        return {}
    
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
                    result = {}
                elif isinstance(market_sentiment, pd.DataFrame):
                    if market_sentiment.empty:
                        logger.info(f"[数据获取] 市场情绪数据为空DataFrame")
                        result = {}
                    else:
                        try:
                            sentiment_dict = {}
                            for _, row in market_sentiment.iterrows():
                                if 'item' in row and 'value' in row:
                                    sentiment_dict[row['item']] = row['value']
                        except Exception as e:
                            logger.error(f"[数据获取] 解析市场情绪DataFrame失败: 错误: {str(e)}")
                            result = {}
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
                        result = {}
            
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
            
            logger.info(f"[数据获取] 获取市场情绪数据成功, 耗时: {end_time - start_time:.2f}s")
            return result
        
        return {}
    
    @performance_monitor
    def get_comprehensive_data(self, stock_code: str) -> Dict[str, Any]:
        stock_info = self.get_stock_info(stock_code)
        kline_data = self.get_kline_data(stock_code)
        financial_data = self.get_financial_data(stock_code)
        fund_flow = self.get_fund_flow(stock_code)
        market_sentiment = self.get_market_sentiment()
        
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
            'market_sentiment': market_sentiment
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
