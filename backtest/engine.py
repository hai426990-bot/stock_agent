import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from .strategy import BaseStrategy

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
