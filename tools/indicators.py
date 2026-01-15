import pandas as pd
import numpy as np

def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """
    Calculate KDJ indicator
    """
    low_list = df['low'].rolling(window=n, min_periods=n).min()
    high_list = df['high'].rolling(window=n, min_periods=n).max()
    rsv = (df['close'] - low_list) / (high_list - low_list) * 100
    
    df_kdj = pd.DataFrame(index=df.index)
    df_kdj['k'] = rsv.ewm(com=m1-1, adjust=False).mean()
    df_kdj['d'] = df_kdj['k'].ewm(com=m2-1, adjust=False).mean()
    df_kdj['j'] = 3 * df_kdj['k'] - 2 * df_kdj['d']
    return df_kdj

def calculate_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR)
    """
    high = df['high']
    low = df['low']
    prev_close = df['close'].shift(1)
    
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=n).mean()
    return atr

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI)
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_bands(series: pd.Series, n: int = 20, k: float = 2.0):
    """
    Calculate Bollinger Bands
    """
    ma = series.rolling(window=n).mean()
    std = series.rolling(window=n).std()
    upper = ma + (k * std)
    lower = ma - (k * std)
    return upper, ma, lower
