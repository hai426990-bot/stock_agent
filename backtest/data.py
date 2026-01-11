import akshare as ak
import pandas as pd
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import time

def retry(max_retries=3, delay=1, backoff=2):
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
                        raise e
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

class DataManager:
    """
    Data layer: Unified market data schema and dataset-level partitioning cache.
    Schema: (dt, open, high, low, close, volume, adj_close)
    """
    def __init__(self, cache_dir: str = ".backtest_cache"):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
    def _get_cache_path(self, symbol: str, freq: str, adjust: str, start_date: str, end_date: str) -> str:
        key = f"{symbol}_{freq}_{adjust}_{start_date}_{end_date}"
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{symbol}_{hash_key}.parquet")

    @retry(max_retries=3)
    def fetch_akshare_data(self, symbol: str, freq: str = "daily", adjust: str = "qfq", 
                          start_date: str = "20200101", end_date: str = None) -> pd.DataFrame:
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
            
        cache_path = self._get_cache_path(symbol, freq, adjust, start_date, end_date)
        
        if os.path.exists(cache_path):
            return pd.read_parquet(cache_path)
        
        # Mapping AkShare data to unified schema
        # AkShare stock_zh_a_hist returns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
        df = ak.stock_zh_a_hist(symbol=symbol, period=period_map.get(freq, "daily"), 
                               start_date=start_date, end_date=end_date, adjust=adjust)
        
        if df.empty:
            return pd.DataFrame()
            
        # Standardize columns
        rename_map = {
            "日期": "dt",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume"
        }
        df = df.rename(columns=rename_map)
        df["dt"] = pd.to_datetime(df["dt"])
        df["adj_close"] = df["close"] # AkShare's close is already adjusted if adjust is set
        
        # Select required columns
        df = df[["dt", "open", "high", "low", "close", "volume", "adj_close"]]
        df = df.sort_values("dt").reset_index(drop=True)
        
        # Save to cache
        df.to_parquet(cache_path)
        return df

    def get_data(self, symbol: str, freq: str = "daily", adjust: str = "qfq", 
                 start_date: str = "20200101", end_date: str = None) -> pd.DataFrame:
        """Unified entry point for data fetching"""
        return self.fetch_akshare_data(symbol, freq, adjust, start_date, end_date)
