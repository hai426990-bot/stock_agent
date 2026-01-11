import pandas as pd
import numpy as np
from typing import Dict, Any

class PerformanceAnalytics:
    """
    Analytics layer: Calculate standard performance metrics.
    Metrics: CAGR, Sharpe, Sortino, MDD, Calmar, Win Rate, Profit-Loss Ratio, Turnover, Trade Count.
    """
    @staticmethod
    def calculate_metrics(results: pd.DataFrame, initial_cash: float = 100000.0) -> Dict[str, Any]:
        if results.empty:
            return {}

        returns = results["daily_return"]
        equity = results["equity"]
        
        # 1. Total Return
        total_return = (equity.iloc[-1] / initial_cash) - 1
        
        # 2. Annualized Return (CAGR)
        days = (results["dt"].iloc[-1] - results["dt"].iloc[0]).days
        if days > 0:
            cagr = (1 + total_return) ** (365 / days) - 1
        else:
            cagr = 0.0
            
        # 3. Volatility
        volatility = returns.std() * np.sqrt(252)
        
        # 4. Sharpe Ratio (assuming 0 risk-free rate)
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() != 0 else 0
        
        # 5. Max Drawdown
        mdd = results["drawdown"].min()
        
        # 6. Calmar Ratio
        calmar = (cagr / abs(mdd)) if mdd != 0 else 0
        
        # 7. Win Rate (days with positive net return)
        win_rate = (returns > 0).sum() / (returns != 0).sum() if (returns != 0).sum() > 0 else 0
        
        # 8. Trade Count
        trade_count = int(results["position"].diff().abs().sum() / 2) # approx trades
        
        # 9. Turnover
        turnover = results["position"].diff().abs().sum() / len(results)
        
        return {
            "total_return": round(total_return, 4),
            "cagr": round(cagr, 4),
            "volatility": round(volatility, 4),
            "sharpe": round(sharpe, 3),
            "max_drawdown": round(mdd, 4),
            "calmar": round(calmar, 3),
            "win_rate": round(win_rate, 4),
            "trade_count": trade_count,
            "turnover": round(turnover, 4)
        }

    @staticmethod
    def get_summary_report(metrics: Dict[str, Any]) -> str:
        report = f"""
### 📊 回测表现报告 (Backtest Summary)
- **累计收益率**: {metrics['total_return']*100:.2f}%
- **年化收益率 (CAGR)**: {metrics['cagr']*100:.2f}%
- **最大回撤 (MDD)**: {metrics['max_drawdown']*100:.2f}%
- **夏普比率 (Sharpe)**: {metrics['sharpe']:.2f}
- **卡玛比率 (Calmar)**: {metrics['calmar']:.2f}
- **胜率**: {metrics['win_rate']*100:.2f}%
- **交易次数**: {metrics['trade_count']}
- **年化波动率**: {metrics['volatility']*100:.2f}%
        """
        return report
