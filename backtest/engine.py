import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from .strategy import BaseStrategy

class TradeSignal:
    def __init__(self, date, signal_type: str, price: float):
        self.date = date
        self.signal_type = signal_type  # "BUY" or "SELL"
        self.price = price
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": str(self.date) if hasattr(self.date, 'isoformat') else str(self.date),
            "type": self.signal_type,
            "price": round(self.price, 4)
        }

class VectorizedEngine:
    """
    Vectorized backtesting engine for fast performance evaluation.
    Supports basic commission and slippage modeling.
    """
    def __init__(self, initial_cash: float = 100000.0, commission: float = 0.0003, slippage: float = 0.001):
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

    def run(self, strategy: BaseStrategy, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run the backtest.
        Returns a result DataFrame with daily returns, positions, and equity curve.
        """
        if df.empty:
            return pd.DataFrame()

        # 1. Generate signals (0 or 1)
        # Shift signal by 1 day because we execute at the next day's open or close
        # Here we assume execution at next day's open or end of current day
        # For simplicity in vectorized, we use current day's close for calculation but shift signals
        positions = strategy.generate_signals(df)
        
        # 2. Calculate daily returns
        # close_to_close returns
        daily_returns = df["close"].pct_change().fillna(0)
        
        # 3. Apply positions (shift positions by 1 to avoid look-ahead bias)
        # The position at day t determines the return from t to t+1
        strategy_positions = positions.shift(1).fillna(0)
        
        # 4. Calculate gross returns
        gross_returns = strategy_positions * daily_returns
        
        # 5. Calculate transaction costs
        # Costs occur when position changes
        trades = strategy_positions.diff().abs().fillna(0)
        # Simple cost model: commission + slippage on trade value
        # In vectorized, we approximate this as a deduction from returns
        transaction_costs = trades * (self.commission + self.slippage)
        
        # 6. Net returns
        net_returns = gross_returns - transaction_costs
        
        # 7. Equity curve
        equity_curve = (1 + net_returns).cumprod() * self.initial_cash
        
        # 8. Combine results
        results = df.copy()
        results["signal"] = positions
        results["position"] = strategy_positions
        results["daily_return"] = net_returns
        results["equity"] = equity_curve
        results["drawdown"] = (equity_curve / equity_curve.cummax()) - 1
        
        return results
    
    def extract_trade_signals(self, results: pd.DataFrame) -> List[TradeSignal]:
        """
        Extract buy and sell signals from backtest results.
        Returns a list of TradeSignal objects.
        """
        signals = []
        if results.empty or "position" not in results.columns:
            return signals
        
        position = results["position"]
        prices = results["close"]
        dates = results["dt"]
        
        for i in range(1, len(position)):
            prev_pos = position.iloc[i-1]
            curr_pos = position.iloc[i]
            
            if curr_pos > prev_pos:  # Buy signal
                signals.append(TradeSignal(dates.iloc[i], "BUY", prices.iloc[i]))
            elif curr_pos < prev_pos:  # Sell signal
                signals.append(TradeSignal(dates.iloc[i], "SELL", prices.iloc[i]))
        
        return signals
