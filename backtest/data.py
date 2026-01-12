import akshare as ak
import pandas as pd
import os
import json
import hashlib
import numpy as np
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
            "成交量": "volume",
            "换手率": "turnover"
        }
        df = df.rename(columns=rename_map)
        df["dt"] = pd.to_datetime(df["dt"])
        df["adj_close"] = df["close"] # AkShare's close is already adjusted if adjust is set
        
        # Select required columns
        df = df[["dt", "open", "high", "low", "close", "volume", "adj_close", "turnover"]]
        df = df.sort_values("dt").reset_index(drop=True)
        
        # Save to cache
        df.to_parquet(cache_path)
        return df

    def get_data(self, symbol: str, freq: str = "daily", adjust: str = "qfq", 
                 start_date: str = "20200101", end_date: str = None, add_indicators: bool = False) -> pd.DataFrame:
        """Unified entry point for data fetching"""
        df = self.fetch_akshare_data(symbol, freq, adjust, start_date, end_date)
        if add_indicators and not df.empty:
            df = self.add_fundamental_indicators(symbol, df)
            df = self.add_macro_indicators(df)
            df = self.add_market_indicators(df)
        return df

    def add_macro_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add macro proxies like PMI"""
        try:
            # Fetch PMI data
            # macro_china_pmi_yearly: 日期, 今值, ...
            pmi_df = ak.macro_china_pmi_yearly()
            if not pmi_df.empty:
                # Filter for official manufacturing PMI
                pmi_df = pmi_df[pmi_df["商品"] == "中国官方制造业PMI"]
                pmi_df = pmi_df[["日期", "今值"]]
                pmi_df.columns = ["month", "pmi"]
                pmi_df["month"] = pd.to_datetime(pmi_df["month"])
                
                # Merge with main df
                df["month"] = df["dt"].dt.to_period("M").dt.to_timestamp()
                df = pd.merge(df, pmi_df, left_on="month", right_on="month", how="left")
                df["pmi"] = pd.to_numeric(df["pmi"], errors="coerce").ffill().bfill().fillna(50.0)
                df = df.drop(columns=["month"])
            else:
                df["pmi"] = 50.0
        except Exception as e:
            print(f"Warning: Failed to add macro indicators: {e}")
            if "pmi" not in df.columns:
                df["pmi"] = 50.0
        return df

    def add_market_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market-wide indicators like volatility and index trend"""
        try:
            # Calculate stock's own volatility (rolling 20-day std of log returns)
            df["returns"] = np.log(df["close"] / df["close"].shift(1))
            df["volatility"] = df["returns"].rolling(window=20).std() * np.sqrt(252)
            
            # Finalize indicators
            df["volatility"] = df["volatility"].ffill().bfill().fillna(0.2) # Default 20%
            
            # Fetch market index (CSI 300) for trend overlay
            try:
                # Use cached or fetch CSI 300
                idx_df = ak.stock_zh_index_daily(symbol="sh000300")
                if not idx_df.empty:
                    idx_df = idx_df.rename(columns={"date": "dt", "close": "idx_close"})
                    idx_df["dt"] = pd.to_datetime(idx_df["dt"])
                    idx_df = idx_df[["dt", "idx_close"]]
                    # Calculate index trend (MA250)
                    idx_df["idx_ma250"] = idx_df["idx_close"].rolling(window=250).mean()
                    idx_df["idx_trend"] = (idx_df["idx_close"] > idx_df["idx_ma250"]).astype(int)
                    
                    df = pd.merge(df, idx_df, on="dt", how="left")
                    df["idx_trend"] = df["idx_trend"].ffill().bfill().fillna(1)
                else:
                    df["idx_trend"] = 1
            except:
                df["idx_trend"] = 1

            # Slow vol proxy
            df["mkt_vol"] = df["volatility"].rolling(window=60).mean() 
            df["mkt_vol"] = df["mkt_vol"].ffill().bfill().fillna(0.2)
            
        except Exception as e:
            print(f"Warning: Failed to add market indicators: {e}")
            if "volatility" not in df.columns: df["volatility"] = 0.2
            if "mkt_vol" not in df.columns: df["mkt_vol"] = 0.2
        return df

    def _parse_chinese_num(self, val):
        """Convert '1.60亿' to 1.6e8, '94.52%' to 0.9452"""
        if isinstance(val, (int, float)):
            return val
        if not isinstance(val, str) or val == 'False':
            return None
        
        val = val.strip()
        if val.endswith('%'):
            try:
                return float(val[:-1]) / 100
            except:
                return None
        
        multipliers = {'亿': 1e8, '万': 1e4}
        for unit, mult in multipliers.items():
            if val.endswith(unit):
                try:
                    return float(val[:-len(unit)]) * mult
                except:
                    return None
        try:
            return float(val)
        except:
            return None

    def add_fundamental_indicators(self, symbol: str, df: pd.DataFrame) -> pd.DataFrame:
        """Add PE, PB, ROE etc. to the price dataframe with fallback mechanism"""
        try:
            # 1. Fetch quarterly financial data (more stable and reliable historical source)
            fin_df = ak.stock_financial_abstract_ths(symbol=symbol)
            if not fin_df.empty:
                # Rename columns for clarity
                fin_df = fin_df.rename(columns={
                    "报告期": "report_date",
                    "净利润": "net_profit",
                    "净利润同比增长率": "net_profit_growth",
                    "营业总收入": "revenue",
                    "营业总收入同比增长率": "revenue_growth",
                    "每股净资产": "bps",
                    "净资产收益率": "roe",
                    "基本每股收益": "eps",
                    "销售毛利率": "gross_margin",
                    "资产负债率": "debt_to_assets",
                    "每股经营现金流": "ocf_ps",
                    "应收账款周转天数": "receivables_days"
                })
                fin_df["report_date"] = pd.to_datetime(fin_df["report_date"])
                
                # Convert strings to numbers
                for col in ["net_profit", "net_profit_growth", "revenue", "revenue_growth", "bps", "roe", "eps", "gross_margin", "debt_to_assets", "ocf_ps", "receivables_days"]:
                    if col in fin_df.columns:
                        fin_df[col] = fin_df[col].apply(self._parse_chinese_num)
                
                # Sort by date
                fin_df = fin_df.sort_values("report_date")
                
                # Merge with price data
                # Use merge_asof to align price date with the latest available report date
                df = df.sort_values("dt")
                available_cols = ["report_date", "net_profit", "net_profit_growth", "revenue", "revenue_growth", "bps", "roe", "eps", "gross_margin", "debt_to_assets", "ocf_ps", "receivables_days"]
                cols_to_merge = [c for c in available_cols if c in fin_df.columns]
                
                df = pd.merge_asof(df, fin_df[cols_to_merge], 
                                  left_on="dt", right_on="report_date", direction="backward")
                
                # Calculate PE, PB if possible
                if "eps" in df.columns and "close" in df.columns:
                    # Rough PE = Close / EPS (LTM approximation)
                    df["pe"] = df["close"] / df["eps"].apply(lambda x: x if x and x > 0 else np.nan)
                if "bps" in df.columns and "close" in df.columns:
                    df["pb"] = df["close"] / df["bps"].apply(lambda x: x if x and x > 0 else np.nan)
                
                # Calculate PEG (PE / (Net Profit Growth * 100))
                if "pe" in df.columns and "net_profit_growth" in df.columns:
                    df["peg"] = df["pe"] / (df["net_profit_growth"] * 100).apply(lambda x: x if x > 0 else np.nan)

                # Calculate FCF Yield proxy (using OCF / Close)
                if "ocf_ps" in df.columns and "close" in df.columns:
                    df["fcf_yield"] = df["ocf_ps"] / df["close"]

            # 2. Estimate Historical Market Cap
            # Try to get current total shares to estimate historical market cap (approximation)
            info_df = ak.stock_individual_info_em(symbol=symbol)
            total_shares = None
            dividend_yield = 0.0
            if not info_df.empty:
                try:
                    # '总股本' is usually the 4th item in stock_individual_info_em
                    res = info_df[info_df["item"] == "总股本"]["value"]
                    if not res.empty:
                        total_shares = float(res.iloc[0])
                    
                    # Also try to get dividend yield (股息率)
                    dy_res = info_df[info_df["item"] == "股息率"]["value"]
                    if not dy_res.empty:
                        dividend_yield = self._parse_chinese_num(dy_res.iloc[0]) or 0.0
                except:
                    pass
            
            if total_shares and "close" in df.columns:
                df["total_mv"] = df["close"] * total_shares
            
            if "dividend_yield" not in df.columns:
                df["dividend_yield"] = dividend_yield

            # 3. Final Fill NaN values (important for signal generation)
            cols_to_fill = ["pe", "pb", "roe", "net_profit_growth", "revenue", "revenue_growth", "peg", "total_mv", "eps", "bps", "gross_margin", "debt_to_assets", "ocf_ps", "receivables_days", "fcf_yield", "dividend_yield", "idx_trend"]
            for col in cols_to_fill:
                if col in df.columns:
                    df[col] = df[col].ffill().bfill().fillna(0)
                else:
                    df[col] = 0.0

        except Exception as e:
            print(f"Warning: Failed to add fundamental indicators for {symbol}: {e}")
            
        return df
