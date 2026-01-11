from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
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

# Advanced Fundamental & Quantitative Combination Strategies

class Value_Revision_Trend_Params(StrategyParams):
    pe_max: float = 20.0
    ma_period: int = 60
    revision_lookback: int = 1  # Compare with previous quarter/period

@register_strategy
class Value_Revision_Trend_Strategy(BaseStrategy):
    """Low Valuation + Earnings Revision + Trend Filter"""
    name = "value_revision_trend"
    
    def get_params_class(self):
        return Value_Revision_Trend_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # 1. Low Valuation (PE < 20)
        low_val = df["pe"] < self.params.pe_max
        
        # 2. Earnings Revision (Profit growth is increasing)
        # Using diff() on net_profit_growth as a proxy for 'upward revision'
        revision_up = df["net_profit_growth"].diff(self.params.revision_lookback) > 0
        
        # 3. Trend Filter (Close > MA60)
        ma = df["close"].rolling(window=self.params.ma_period).mean()
        trend_ok = df["close"] > ma
        
        return (low_val & revision_up & trend_ok).astype(int)

class Quality_Growth_PEG_Params(StrategyParams):
    roe_min: float = 15.0
    peg_min: float = 0.5
    peg_max: float = 1.5
    strong_roe: float = 20.0
    strong_peg_max: float = 1.2

@register_strategy
class Quality_Growth_PEG_Strategy(BaseStrategy):
    """Quality Growth + PEG + Graded Positioning"""
    name = "quality_growth_peg"
    
    def get_params_class(self):
        return Quality_Growth_PEG_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Quality (ROE)
        is_quality = df["roe"] > self.params.roe_min
        is_strong_quality = df["roe"] > self.params.strong_roe
        
        # Valuation (PEG)
        peg_ok = (df["peg"] > self.params.peg_min) & (df["peg"] < self.params.peg_max)
        strong_peg_ok = (df["peg"] > self.params.peg_min) & (df["peg"] < self.params.strong_peg_max)
        
        # Graded Positioning
        position = pd.Series(0.0, index=df.index)
        
        # Moderate condition (60% position)
        position[(is_quality & peg_ok)] = 0.6
        
        # Strong condition (100% position)
        position[(is_strong_quality & strong_peg_ok)] = 1.0
        
        return position

class Leader_Momentum_Drawdown_Params(StrategyParams):
    momentum_period: int = 20
    stop_loss: float = -0.08  # 8% stop loss
    # Since we don't have industry context in a single-stock backtest, 
    # we'll use a absolute market cap threshold or just momentum + drawdown.
    # For a multi-stock system, 'Leader' would be ranking.
    market_cap_min: float = 500.0  # e.g., 50B CNY (in 100M units)

@register_strategy
class Leader_Momentum_Drawdown_Strategy(BaseStrategy):
    """Leader + Momentum + Drawdown Control"""
    name = "leader_momentum_drawdown"
    
    def get_params_class(self):
        return Leader_Momentum_Drawdown_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # 1. Leader (Market Cap)
        # Note: total_mv in AkShare lg is usually in 100M or absolute units.
        is_leader = df["total_mv"] > self.params.market_cap_min
        
        # 2. Momentum (Price change over period)
        momentum = df["close"].pct_change(self.params.momentum_period) > 0
        
        # 3. Drawdown Control
        # Calculate trailing high for drawdown control
        rolling_max = df["close"].expanding().max()
        drawdown = (df["close"] / rolling_max) - 1
        drawdown_ok = drawdown > self.params.stop_loss
        
        position = pd.Series(0, index=df.index)
        holding = 0
        for i in range(len(df)):
            # Entry: Leader + Momentum + Drawdown OK
            if holding == 0:
                if is_leader.iloc[i] and momentum.iloc[i] and drawdown_ok.iloc[i]:
                    holding = 1
            # Exit: Drawdown Control (Stop Loss)
            elif holding == 1:
                if not drawdown_ok.iloc[i]:
                    holding = 0
            position.iloc[i] = holding
            
        return position

# --- New Complex Strategies ---

class HighMargin_Momentum_Industry_Params(StrategyParams):
    margin_min: float = 0.20  # 20% Gross Margin
    momentum_period: int = 20
    relative_strength_min: float = 1.05  # 5% better than market/avg

@register_strategy
class HighMargin_Momentum_Industry_Strategy(BaseStrategy):
    """High Margin + Price Momentum + Industry Strength (Relative to market)"""
    name = "high_margin_momentum_industry"
    
    def get_params_class(self):
        return HighMargin_Momentum_Industry_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # 1. High Margin
        high_margin = df["gross_margin"] > self.params.margin_min
        
        # 2. Price Momentum
        momentum = df["close"].pct_change(self.params.momentum_period) > 0
        
        # 3. Industry Strength (Proxy: Stock vs its own 250-day moving average)
        # In a real industry strategy, this would be Industry Index Strength.
        ma250 = df["close"].rolling(window=250).mean()
        strength = df["close"] > (ma250 * self.params.relative_strength_min)
        
        return (high_margin & momentum & strength).astype(int)

class Prosperity_Rotation_Params(StrategyParams):
    pmi_threshold: float = 50.0  # Expansion threshold
    roe_min: float = 0.10
    net_profit_growth_min: float = 0.0

@register_strategy
class Prosperity_Rotation_Strategy(BaseStrategy):
    """Prosperity Rotation (PMI) + Stock Quality (ROE/Growth)"""
    name = "prosperity_rotation"
    
    def get_params_class(self):
        return Prosperity_Rotation_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # 1. Macro Prosperity (PMI > 50)
        pmi_ok = df["pmi"] > self.params.pmi_threshold
        
        # 2. Quality & Growth
        quality = df["roe"] > self.params.roe_min
        growth = df["net_profit_growth"] > self.params.net_profit_growth_min
        
        # Only invest when macro is in expansion and quality is high
        return (pmi_ok & quality & growth).astype(int)

class Defensive_Offensive_Switch_Params(StrategyParams):
    vol_threshold: float = 0.30  # 30% annualized volatility threshold
    momentum_period: int = 20
    low_vol_window: int = 60

@register_strategy
class Defensive_Offensive_Switch_Strategy(BaseStrategy):
    """Switch: High Vol Period -> Low Vol/Defensive, Low Vol Period -> Momentum/Offensive"""
    name = "defensive_offensive_switch"
    
    def get_params_class(self):
        return Defensive_Offensive_Switch_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Market Volatility Proxy (from DataManager)
        is_high_vol = df["mkt_vol"] > self.params.vol_threshold
        
        # Offensive Signal: Momentum
        offensive_signal = df["close"].pct_change(self.params.momentum_period) > 0
        
        # Defensive Signal: Low Volatility (Stock's own volatility is below its mean)
        avg_vol = df["volatility"].rolling(window=self.params.low_vol_window).mean()
        defensive_signal = df["volatility"] < avg_vol
        
        position = pd.Series(0, index=df.index)
        for i in range(len(df)):
            if is_high_vol.iloc[i]:
                # Defensive mode: only hold if stock is low vol
                position.iloc[i] = 1 if defensive_signal.iloc[i] else 0
            else:
                # Offensive mode: hold if momentum is positive
                position.iloc[i] = 1 if offensive_signal.iloc[i] else 0
                
        return position

class Leader_Valuation_Weight_Params(StrategyParams):
    market_cap_min: float = 1000.0  # 100B Leader
    pe_cheap: float = 15.0
    pe_expensive: float = 40.0

@register_strategy
class Leader_Valuation_Weight_Strategy(BaseStrategy):
    """Leader + Valuation Stratification (Weighting: Cheap = 1.0, Expensive = 0.3)"""
    name = "leader_valuation_weight"
    
    def get_params_class(self):
        return Leader_Valuation_Weight_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        is_leader = df["total_mv"] > self.params.market_cap_min
        
        position = pd.Series(0.0, index=df.index)
        for i in range(len(df)):
            if is_leader.iloc[i]:
                pe = df["pe"].iloc[i]
                if pe < self.params.pe_cheap:
                    position.iloc[i] = 1.0
                elif pe < self.params.pe_expensive:
                    position.iloc[i] = 0.5
                else:
                    position.iloc[i] = 0.2
            else:
                position.iloc[i] = 0.0
                
        return position

class Value_Momentum_Quality_Params(StrategyParams):
    lookback: int = 20

@register_strategy
class Value_Momentum_Quality_Strategy(BaseStrategy):
    """Combined Factor Score (1/3 each: Value, Momentum, Quality)"""
    name = "value_momentum_quality_score"
    
    def get_params_class(self):
        return Value_Momentum_Quality_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Normalize factors (0 to 1 score)
        # 1. Value (Inverse PE: lower PE is better)
        value_score = 1.0 / df["pe"].replace(0, np.nan)
        value_score = (value_score - value_score.rolling(250).min()) / (value_score.rolling(250).max() - value_score.rolling(250).min())
        
        # 2. Momentum (Return over lookback)
        mom_score = df["close"].pct_change(self.params.lookback)
        mom_score = (mom_score - mom_score.rolling(250).min()) / (mom_score.rolling(250).max() - mom_score.rolling(250).min())
        
        # 3. Quality (ROE)
        quality_score = df["roe"]
        quality_score = (quality_score - quality_score.rolling(250).min()) / (quality_score.rolling(250).max() - quality_score.rolling(250).min())
        
        combined_score = (value_score + mom_score + quality_score) / 3.0
        
        # Signal: Top 30% of its own history
        threshold = combined_score.rolling(250).quantile(0.7)
        return (combined_score > threshold).astype(int)

# --- 实盘进阶策略 (Execution-Ready Advanced Strategies) ---

class LowVal_DebtRepair_Params(StrategyParams):
    pe_max: float = 30.0
    debt_reduction_lookback: int = 20  # Days to check for debt reduction trend

@register_strategy
class LowVal_DebtRepair_Strategy(BaseStrategy):
    """低估值 + 资产负债表修复 (Low PE + Decreasing Debt Ratio)"""
    name = "lowval_debt_repair"
    
    def get_params_class(self):
        return LowVal_DebtRepair_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        low_val = df["pe"] < self.params.pe_max
        debt_repair = df["debt_to_assets"].diff(self.params.debt_reduction_lookback) < 0
        return (low_val & debt_repair).astype(int)

class Leader_Quality_Value_Params(StrategyParams):
    market_cap_min: float = 500.0  # 50B Leader proxy
    roe_min: float = 0.12
    pe_max: float = 40.0

@register_strategy
class Leader_Quality_Value_Strategy(BaseStrategy):
    """龙头价值 (Leader + Quality + Fair Valuation)"""
    name = "leader_quality_value"
    
    def get_params_class(self):
        return Leader_Quality_Value_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        is_leader = df["total_mv"] > self.params.market_cap_min
        is_quality = df["roe"] > self.params.roe_min
        is_fair_val = df["pe"] < self.params.pe_max
        return (is_leader & is_quality & is_fair_val).astype(int)

class Dividend_LowVol_Trend_Params(StrategyParams):
    dividend_min: float = 0.015  # 1.5% yield
    vol_window: int = 60
    ma_trend: int = 250

@register_strategy
class Dividend_LowVol_Trend_Strategy(BaseStrategy):
    """红利低波 + 趋势过滤 (Dividend + Low Vol + Trend Filter)"""
    name = "dividend_lowvol_trend"
    
    def get_params_class(self):
        return Dividend_LowVol_Trend_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # High Dividend
        high_div = df["dividend_yield"] > self.params.dividend_min
        
        # Low Volatility (Stock's vol < its 60-day avg)
        avg_vol = df["volatility"].rolling(window=self.params.vol_window).mean()
        low_vol = df["volatility"] < avg_vol
        
        # Trend Filter (Close > MA250)
        ma250 = df["close"].rolling(window=self.params.ma_trend).mean()
        trend_ok = df["close"] > ma250
        
        return (high_div & low_vol & trend_ok).astype(int)

class Momentum_Liquidity_Params(StrategyParams):
    momentum_period: int = 20
    turnover_max: float = 5.0  # Filter out turnover spikes (in %)
    market_cap_min: float = 500.0

@register_strategy
class Momentum_Liquidity_Strategy(BaseStrategy):
    """动量 + 换手过滤 + 流动性分层 (Momentum + Turnover Filter + Liquidity)"""
    name = "momentum_liquidity"
    
    def get_params_class(self):
        return Momentum_Liquidity_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Momentum
        momentum = df["close"].pct_change(self.params.momentum_period) > 0
        
        # Turnover filter (avoid speculative spikes)
        turnover_ok = df["turnover"] < self.params.turnover_max
        
        # Liquidity (Market Cap as proxy)
        is_liquid = df["total_mv"] > self.params.market_cap_min
        
        return (momentum & turnover_ok & is_liquid).astype(int)

class Quality_Value_Stable_Params(StrategyParams):
    pe_max: float = 40.0
    pb_max: float = 5.0
    margin_stability: float = -0.01  # Max margin drop
    receivables_max: int = 120  # Days

@register_strategy
class Quality_Value_Stable_Strategy(BaseStrategy):
    """质量价值 (EP/BP + 毛利稳定 + 低应收)"""
    name = "quality_value_stable"
    
    def get_params_class(self):
        return Quality_Value_Stable_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Value (PE, PB)
        is_cheap = (df["pe"] < self.params.pe_max) & (df["pb"] < self.params.pb_max)
        
        # Stability (Gross Margin not dropping sharply)
        margin_stable = df["gross_margin"].diff(20) > self.params.margin_stability
        
        # Quality (Low receivables days)
        low_receivables = df["receivables_days"] < self.params.receivables_max
        
        return (is_cheap & margin_stable & low_receivables).astype(int)

class FCF_NoTrap_Params(StrategyParams):
    fcf_yield_min: float = 0.015
    revision_period: int = 20
    debt_max: float = 0.60

@register_strategy
class FCF_NoTrap_Strategy(BaseStrategy):
    """价值不陷阱 (FCF Yield + 盈利上修 + 低杠杆)"""
    name = "fcf_no_trap"
    
    def get_params_class(self):
        return FCF_NoTrap_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # High FCF Yield
        high_fcf = df["fcf_yield"] > self.params.fcf_yield_min
        
        # Earnings Revision Proxy (Profit growth trending up)
        revision_up = df["net_profit_growth"].diff(self.params.revision_period) > 0
        
        # Low Leverage
        low_leverage = df["debt_to_assets"] < self.params.debt_max
        
        return (high_fcf & revision_up & low_leverage).astype(int)

class Reversion_Value_Industry_Params(StrategyParams):
    reversion_period: int = 20
    pe_max: float = 30.0
    idx_trend_filter: bool = True

@register_strategy
class Reversion_Value_Industry_Strategy(BaseStrategy):
    """反转 + 价值过滤 + 行业中性 (Control Style Drift)"""
    name = "reversion_value_industry"
    
    def get_params_class(self):
        return Reversion_Value_Industry_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Reversion (Price dropped over period)
        reversion = df["close"].pct_change(self.params.reversion_period) < -0.05
        
        # Value filter
        is_cheap = df["pe"] < self.params.pe_max
        
        # Index Trend Filter (Only buy when market is not in crash)
        trend_ok = df["idx_trend"] == 1 if self.params.idx_trend_filter else True
        
        return (reversion & is_cheap & trend_ok).astype(int)

class Tech_Prosperity_Params(StrategyParams):
    rev_accel_period: int = 20
    momentum_period: int = 20
    gross_margin_min: float = 0.30

@register_strategy
class Tech_Prosperity_Strategy(BaseStrategy):
    """科技景气 (Revenue Accel + Momentum + High Margin)"""
    name = "tech_prosperity"
    
    def get_params_class(self):
        return Tech_Prosperity_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Revenue Acceleration
        rev_accel = df["revenue_growth"].diff(self.params.rev_accel_period) > 0
        
        # Price Momentum
        momentum = df["close"].pct_change(self.params.momentum_period) > 0
        
        # High Gross Margin (Proxy for R&D/Tech value)
        high_margin = df["gross_margin"] > self.params.gross_margin_min
        
        return (rev_accel & momentum & high_margin).astype(int)

class Shareholder_Return_Params(StrategyParams):
    dividend_min: float = 0.02
    vol_window: int = 60
    roe_min: float = 0.12

@register_strategy
class Shareholder_Return_Strategy(BaseStrategy):
    """股东回报 (Dividend + Low Vol + Quality)"""
    name = "shareholder_return"
    
    def get_params_class(self):
        return Shareholder_Return_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # High Dividend (Proxy for total return)
        high_div = df["dividend_yield"] > self.params.dividend_min
        
        # Low Vol
        avg_vol = df["volatility"].rolling(window=self.params.vol_window).mean()
        low_vol = df["volatility"] < avg_vol
        
        # Quality (ROE)
        quality = df["roe"] > self.params.roe_min
        
        return (high_div & low_vol & quality).astype(int)

class Drawdown_Control_Momentum_Params(StrategyParams):
    momentum_period: int = 20
    mdd_threshold: float = -0.10
    stop_loss_window: int = 5

@register_strategy
class Drawdown_Control_Momentum_Strategy(BaseStrategy):
    """回撤熔断 + 动量 (Momentum + Risk Control)"""
    name = "drawdown_control_momentum"
    
    def get_params_class(self):
        return Drawdown_Control_Momentum_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Momentum
        momentum = df["close"].pct_change(self.params.momentum_period) > 0
        
        # Drawdown calculation
        rolling_max = df["close"].expanding().max()
        drawdown = (df["close"] / rolling_max) - 1
        
        # Risk Switch: Circuit breaker if drawdown > threshold
        circuit_ok = (drawdown > self.params.mdd_threshold).rolling(window=self.params.stop_loss_window).min() > 0
        
        return (momentum & circuit_ok).astype(int)

class Volatility_Target_Params(StrategyParams):
    vol_target: float = 0.15  # 15% Target Vol
    momentum_period: int = 20

@register_strategy
class Volatility_Target_Strategy(BaseStrategy):
    """波动率目标 + 多因子 (Volatility Target)"""
    name = "vol_target_multi_factor"
    
    def get_params_class(self):
        return Volatility_Target_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Momentum signal
        momentum = df["close"].pct_change(self.params.momentum_period) > 0
        
        # Position sizing based on volatility target
        # weight = Target Vol / Current Vol
        vol = df["volatility"].replace(0, 0.2)
        target_weight = self.params.vol_target / vol
        target_weight = target_weight.clip(0, 1.0)
        
        return (momentum.astype(float) * target_weight)

class Index_Trend_Overlay_Params(StrategyParams):
    ma_fast: int = 20
    ma_slow: int = 60

@register_strategy
class Index_Trend_Overlay_Strategy(BaseStrategy):
    """指数趋势 overlay + 多因子底仓 (Index Trend Overlay)"""
    name = "index_trend_overlay"
    
    def get_params_class(self):
        return Index_Trend_Overlay_Params
        
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        # Multi-factor base (Value + Quality)
        is_quality_value = (df["roe"] > 0.10) & (df["pe"] < 30)
        
        # Index Trend Filter
        idx_trend = df["idx_trend"] == 1
        
        return (is_quality_value & idx_trend).astype(int)

