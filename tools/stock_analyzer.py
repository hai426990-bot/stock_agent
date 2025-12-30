import pandas as pd
import numpy as np
from typing import Dict, Any

class StockAnalyzer:
    @staticmethod
    def calculate_ma(data: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> Dict[str, float]:
        ma_dict = {}
        for period in periods:
            if len(data) >= period:
                ma_dict[f'MA{period}'] = data['收盘'].rolling(window=period).mean().iloc[-1]
        return ma_dict
    
    @staticmethod
    def calculate_macd(data: pd.DataFrame) -> Dict[str, Any]:
        if len(data) < 26:
            return {}
        
        close_prices = data['收盘'].values
        ema12 = pd.Series(close_prices).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(close_prices).ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd = (dif - dea) * 2
        
        return {
            'DIF': round(dif.iloc[-1], 2),
            'DEA': round(dea.iloc[-1], 2),
            'MACD': round(macd.iloc[-1], 2),
            'signal': '金叉' if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2] else '死叉' if dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2] else '无'
        }
    
    @staticmethod
    def calculate_kdj(data: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, Any]:
        if len(data) < n:
            return {}
        
        low_list = data['最低'].rolling(window=n, min_periods=1).min()
        high_list = data['最高'].rolling(window=n, min_periods=1).max()
        rsv = (data['收盘'] - low_list) / (high_list - low_list) * 100
        
        k = rsv.ewm(com=m1 - 1, adjust=False).mean()
        d = k.ewm(com=m2 - 1, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return {
            'K': round(k.iloc[-1], 2),
            'D': round(d.iloc[-1], 2),
            'J': round(j.iloc[-1], 2),
            'signal': '超买' if k.iloc[-1] > 80 else '超卖' if k.iloc[-1] < 20 else '正常'
        }
    
    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> Dict[str, Any]:
        if len(data) < period + 1:
            return {}
        
        delta = data['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return {
            'RSI': round(rsi.iloc[-1], 2),
            'signal': '超买' if rsi.iloc[-1] > 70 else '超卖' if rsi.iloc[-1] < 30 else '正常'
        }
    
    @staticmethod
    def calculate_boll(data: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict[str, Any]:
        if len(data) < period:
            return {}
        
        sma = data['收盘'].rolling(window=period).mean()
        std = data['收盘'].rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        current_price = data['收盘'].iloc[-1]
        
        return {
            'MID': round(sma.iloc[-1], 2),
            'UPPER': round(upper_band.iloc[-1], 2),
            'LOWER': round(lower_band.iloc[-1], 2),
            'position': '上轨附近' if current_price > upper_band.iloc[-1] * 0.98 else '下轨附近' if current_price < lower_band.iloc[-1] * 1.02 else '中轨附近'
        }
    
    @staticmethod
    def calculate_volume_ratio(data: pd.DataFrame) -> Dict[str, Any]:
        if len(data) < 5:
            return {}
        
        avg_volume_5 = data['成交量'].tail(5).mean()
        avg_volume_10 = data['成交量'].tail(10).mean()
        current_volume = data['成交量'].iloc[-1]
        
        return {
            'volume_ratio_5': round(current_volume / avg_volume_5, 2),
            'volume_ratio_10': round(current_volume / avg_volume_10, 2),
            'signal': '放量' if current_volume > avg_volume_5 * 1.5 else '缩量' if current_volume < avg_volume_5 * 0.7 else '正常'
        }
    
    @staticmethod
    def identify_patterns(data: pd.DataFrame) -> Dict[str, Any]:
        patterns = []
        
        if len(data) < 10:
            return {'patterns': patterns}
        
        recent = data.tail(10)
        
        highs = recent['最高'].values
        lows = recent['最低'].values
        
        if len(highs) >= 5:
            if highs[0] > highs[2] and highs[2] > highs[4]:
                patterns.append('下降趋势')
            elif highs[0] < highs[2] and highs[2] < highs[4]:
                patterns.append('上升趋势')
        
        if len(lows) >= 5:
            if lows[0] > lows[2] and lows[2] > lows[4]:
                patterns.append('底部抬高')
            elif lows[0] < lows[2] and lows[2] < lows[4]:
                patterns.append('底部降低')
        
        if len(recent) >= 3:
            if recent['收盘'].iloc[-1] > recent['开盘'].iloc[-1] and \
               recent['收盘'].iloc[-2] > recent['开盘'].iloc[-2] and \
               recent['收盘'].iloc[-3] > recent['开盘'].iloc[-3]:
                patterns.append('三连阳')
            elif recent['收盘'].iloc[-1] < recent['开盘'].iloc[-1] and \
                 recent['收盘'].iloc[-2] < recent['开盘'].iloc[-2] and \
                 recent['收盘'].iloc[-3] < recent['开盘'].iloc[-3]:
                patterns.append('三连阴')
        
        return {'patterns': patterns if patterns else ['无明显形态']}
    
    @staticmethod
    def calculate_support_resistance(data: pd.DataFrame) -> Dict[str, Any]:
        if len(data) < 20:
            return {}
        
        recent = data.tail(20)
        
        resistance_levels = []
        support_levels = []
        
        for i in range(1, len(recent) - 1):
            if recent['最高'].iloc[i] > recent['最高'].iloc[i-1] and \
               recent['最高'].iloc[i] > recent['最高'].iloc[i+1]:
                resistance_levels.append(float(recent['最高'].iloc[i]))
            
            if recent['最低'].iloc[i] < recent['最低'].iloc[i-1] and \
               recent['最低'].iloc[i] < recent['最低'].iloc[i+1]:
                support_levels.append(float(recent['最低'].iloc[i]))
        
        resistance_levels.sort(reverse=True)
        support_levels.sort()
        
        current_price = float(data['收盘'].iloc[-1])
        
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=None)
        nearest_support = max([s for s in support_levels if s < current_price], default=None)
        
        return {
            'resistance_levels': resistance_levels[:3],
            'support_levels': support_levels[:3],
            'nearest_resistance': round(nearest_resistance, 2) if nearest_resistance else None,
            'nearest_support': round(nearest_support, 2) if nearest_support else None
        }
    
    @staticmethod
    def calculate_volatility(data: pd.DataFrame, period: int = 20) -> Dict[str, Any]:
        if len(data) < period:
            return {}
        
        returns = data['收盘'].pct_change().dropna()
        
        volatility_daily = returns.tail(period).std()
        volatility_annual = volatility_daily * (252 ** 0.5)
        
        return {
            'volatility_daily': round(volatility_daily, 4),
            'volatility_annual': round(volatility_annual, 4)
        }
    
    @staticmethod
    def calculate_max_drawdown(data: pd.DataFrame) -> Dict[str, Any]:
        if len(data) < 2:
            return {}
        
        cumulative = (1 + data['收盘'].pct_change()).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        
        max_drawdown = drawdown.min()
        
        max_drawdown_idx = drawdown.idxmin()
        peak_idx = cumulative.loc[:max_drawdown_idx].idxmax()
        
        peak_price = float(data.loc[peak_idx, '收盘'])
        trough_price = float(data.loc[max_drawdown_idx, '收盘'])
        
        return {
            'max_drawdown': round(max_drawdown, 4),
            'max_drawdown_pct': round(abs(max_drawdown) * 100, 2),
            'peak_price': round(peak_price, 2),
            'trough_price': round(trough_price, 2),
            'peak_date': str(peak_idx),
            'trough_date': str(max_drawdown_idx)
        }
    
    @staticmethod
    def calculate_risk_metrics(data: pd.DataFrame, risk_free_rate: float = 0.03) -> Dict[str, Any]:
        if len(data) < 60:
            return {}
        
        returns = data['收盘'].pct_change().dropna()
        
        volatility = returns.std()
        annual_return = (1 + returns.mean()) ** 252 - 1
        sharpe_ratio = (annual_return - risk_free_rate) / (volatility * (252 ** 0.5))
        
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = (annual_return - risk_free_rate) / (downside_std * (252 ** 0.5)) if downside_std > 0 else 0
        
        return {
            'volatility': round(volatility, 4),
            'annual_return': round(annual_return, 4),
            'sharpe_ratio': round(sharpe_ratio, 4),
            'sortino_ratio': round(sortino_ratio, 4)
        }
    
    @staticmethod
    def analyze_technical_indicators(stock_data: Dict[str, Any]) -> Dict[str, Any]:
        kline_data = stock_data.get('kline_data', pd.DataFrame())
        
        if isinstance(kline_data, pd.DataFrame):
            kline_df = kline_data
        elif isinstance(kline_data, list) and len(kline_data) > 0:
            try:
                kline_df = pd.DataFrame(kline_data)
            except Exception as e:
                return {}
        else:
            return {}
        
        if kline_df.empty:
            return {}
        
        ma = StockAnalyzer.calculate_ma(kline_df)
        macd = StockAnalyzer.calculate_macd(kline_df)
        kdj = StockAnalyzer.calculate_kdj(kline_df)
        rsi = StockAnalyzer.calculate_rsi(kline_df)
        boll = StockAnalyzer.calculate_boll(kline_df)
        volume_ratio = StockAnalyzer.calculate_volume_ratio(kline_df)
        patterns = StockAnalyzer.identify_patterns(kline_df)
        support_resistance = StockAnalyzer.calculate_support_resistance(kline_df)
        volatility = StockAnalyzer.calculate_volatility(kline_df)
        max_drawdown = StockAnalyzer.calculate_max_drawdown(kline_df)
        risk_metrics = StockAnalyzer.calculate_risk_metrics(kline_df)
        
        return {
            'ma': ma,
            'macd': macd,
            'kdj': kdj,
            'rsi': rsi,
            'boll': boll,
            'volume_ratio': volume_ratio,
            'patterns': patterns,
            'support_resistance': support_resistance,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'risk_metrics': risk_metrics
        }
