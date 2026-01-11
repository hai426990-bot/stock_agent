from abc import ABC, abstractmethod
import pandas as pd
from pydantic import BaseModel
from typing import Dict, Type, Any

class StrategyParams(BaseModel):
    """Base class for strategy parameters using Pydantic validation"""
    pass

class BaseStrategy(ABC):
    """
    Base strategy class. 
    Strategies must implement the generate_signals method.
    """
    name: str = "BaseStrategy"
    
    def __init__(self, params: Dict[str, Any] = None):
        self.params = self.get_params_class()(**(params or {}))

    @abstractmethod
    def get_params_class(self) -> Type[StrategyParams]:
        """Return the Pydantic model class for parameters"""
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate target position signals.
        Returns a pd.Series of target weights/positions (e.g., 0 or 1).
        """
        pass

# Strategy Registry
STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {}

def register_strategy(cls: Type[BaseStrategy]):
    STRATEGY_REGISTRY[cls.name] = cls
    return cls

# Example Strategies

class MA_Crossover_Params(StrategyParams):
    fast: int = 10
    slow: int = 30

@register_strategy
class MA_Crossover_Strategy(BaseStrategy):
    name = "ma_crossover"
    
    def get_params_class(self):
        return MA_Crossover_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        fast_ma = df["close"].rolling(window=self.params.fast).mean()
        slow_ma = df["close"].rolling(window=self.params.slow).mean()
        # 1 for long, 0 for cash
        signals = (fast_ma > slow_ma).astype(int)
        return signals

class RSI_Params(StrategyParams):
    period: int = 14
    buy_threshold: float = 30.0
    sell_threshold: float = 70.0

@register_strategy
class RSI_Strategy(BaseStrategy):
    name = "rsi_reversion"
    
    def get_params_class(self):
        return RSI_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.params.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        position = pd.Series(0, index=df.index)
        holding = 0
        for i in range(len(df)):
            if holding == 0 and rsi.iloc[i] < self.params.buy_threshold:
                holding = 1
            elif holding == 1 and rsi.iloc[i] > self.params.sell_threshold:
                holding = 0
            position.iloc[i] = holding
        return position

class MACD_Params(StrategyParams):
    fast: int = 12
    slow: int = 26
    signal: int = 9

@register_strategy
class MACD_Strategy(BaseStrategy):
    name = "macd_trend"
    
    def get_params_class(self):
        return MACD_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        exp1 = df["close"].ewm(span=self.params.fast, adjust=False).mean()
        exp2 = df["close"].ewm(span=self.params.slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=self.params.signal, adjust=False).mean()
        return (macd > signal_line).astype(int)

# Multi-Indicator Combination Strategies

class Trend_Momentum_Params(StrategyParams):
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_period: int = 14
    rsi_buy_max: float = 65.0  # Avoid buying when already overbought

@register_strategy
class Trend_Momentum_Strategy(BaseStrategy):
    """Combines Trend (MACD) and Momentum (RSI)"""
    name = "trend_momentum_combo"
    
    def get_params_class(self):
        return Trend_Momentum_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # MACD
        exp1 = df["close"].ewm(span=self.params.macd_fast, adjust=False).mean()
        exp2 = df["close"].ewm(span=self.params.macd_slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=self.params.macd_signal, adjust=False).mean()
        macd_bullish = macd > signal_line
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.params.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Signals: MACD cross up AND RSI not overbought
        return (macd_bullish & (rsi < self.params.rsi_buy_max)).astype(int)

class MeanReversion_Volatility_Params(StrategyParams):
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0

@register_strategy
class MeanReversion_Volatility_Strategy(BaseStrategy):
    """Combines Volatility (Bollinger) and Momentum (RSI) for Mean Reversion"""
    name = "mean_reversion_volatility"
    
    def get_params_class(self):
        return MeanReversion_Volatility_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Bollinger Bands
        ma = df["close"].rolling(window=self.params.bb_period).mean()
        std = df["close"].rolling(window=self.params.bb_period).std()
        lower_band = ma - (self.params.bb_std * std)
        upper_band = ma + (self.params.bb_std * std)
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.params.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        position = pd.Series(0, index=df.index)
        holding = 0
        for i in range(len(df)):
            # Buy when price below lower band AND RSI oversold
            if holding == 0:
                if df["close"].iloc[i] < lower_band.iloc[i] and rsi.iloc[i] < self.params.rsi_oversold:
                    holding = 1
            # Sell when price above upper band OR RSI overbought
            elif holding == 1:
                if df["close"].iloc[i] > upper_band.iloc[i] or rsi.iloc[i] > self.params.rsi_overbought:
                    holding = 0
            position.iloc[i] = holding
        return position

class Volume_Trend_Params(StrategyParams):
    fast_ma: int = 5
    slow_ma: int = 20
    volume_period: int = 20
    volume_factor: float = 1.2  # Volume must be 1.2x average

@register_strategy
class VolumeTrend_Strategy(BaseStrategy):
    """Combines Trend (MA) and Volume confirmation"""
    name = "volume_trend_confirmation"
    
    def get_params_class(self):
        return Volume_Trend_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        fast_ma = df["close"].rolling(window=self.params.fast_ma).mean()
        slow_ma = df["close"].rolling(window=self.params.slow_ma).mean()
        
        avg_volume = df["volume"].rolling(window=self.params.volume_period).mean()
        volume_confirm = df["volume"] > (avg_volume * self.params.volume_factor)
        
        # Trend is up
        trend_up = fast_ma > slow_ma
        
        # Signal: Trend up AND Volume confirmation
        return (trend_up & volume_confirm).astype(int)
