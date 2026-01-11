from typing import Dict, Any, List, Optional

import pandas as pd


def _get_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _backtest_positions(close: pd.Series, position: pd.Series) -> Dict[str, Any]:
    returns = close.pct_change().fillna(0)
    strategy_returns = (position.shift(1).fillna(0) * returns).fillna(0)

    equity = (1 + strategy_returns).cumprod()
    total_return = float(equity.iloc[-1] - 1) if not equity.empty else 0.0

    if len(strategy_returns) > 1:
        ann_return = (1 + total_return) ** (252 / len(strategy_returns)) - 1
    else:
        ann_return = 0.0

    ret_std = strategy_returns.std()
    sharpe = 0.0
    if ret_std and ret_std != 0:
        sharpe = (strategy_returns.mean() / ret_std) * (252 ** 0.5)

    rolling_max = equity.cummax()
    drawdown = (equity / rolling_max) - 1
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    trades = int(((position.shift(1).fillna(0) == 0) & (position == 1)).sum())

    return {
        "total_return": round(total_return, 4),
        "annual_return": round(float(ann_return), 4),
        "sharpe": round(float(sharpe), 3),
        "max_drawdown": round(float(max_drawdown), 4),
        "trades": trades,
    }


def _ma_crossover(close: pd.Series, fast: int = 10, slow: int = 30) -> pd.Series:
    fast_ma = close.rolling(window=fast).mean()
    slow_ma = close.rolling(window=slow).mean()
    return (fast_ma > slow_ma).astype(int)


def _rsi_reversion(close: pd.Series, period: int = 14, buy: float = 30, sell: float = 50) -> pd.Series:
    rsi = _calc_rsi(close, period=period)
    position = pd.Series(0, index=close.index)
    holding = 0
    for i in range(len(close)):
        if holding == 0 and rsi.iloc[i] < buy:
            holding = 1
        elif holding == 1 and rsi.iloc[i] > sell:
            holding = 0
        position.iloc[i] = holding
    return position


def _bollinger_breakout(close: pd.Series, window: int = 20, band: float = 2.0) -> pd.Series:
    mid = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper = mid + band * std
    position = pd.Series(0, index=close.index)
    holding = 0
    for i in range(len(close)):
        if holding == 0 and close.iloc[i] > upper.iloc[i]:
            holding = 1
        elif holding == 1 and close.iloc[i] < mid.iloc[i]:
            holding = 0
        position.iloc[i] = holding
    return position


def _macd_trend(close: pd.Series) -> pd.Series:
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    position = (macd > signal).astype(int)
    return position


def select_best_strategy(df: pd.DataFrame) -> Dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"error": "no_price_data", "strategies": []}

    close_col = _get_col(df, ["收盘", "close", "Close", "收盘价"])
    if not close_col:
        return {"error": "missing_close_column", "strategies": []}

    date_col = _get_col(df, ["日期", "date", "Date"])
    if date_col:
        df = df.sort_values(date_col)
    else:
        df = df.sort_index()
    close = df[close_col].astype(float).dropna()

    if close.empty:
        return {"error": "empty_close_series", "strategies": []}

    if len(close) < 60:
        return {"error": "insufficient_history", "lookback_days": len(close), "strategies": []}

    strategies = {
        "ma_crossover": _ma_crossover(close),
        "rsi_reversion": _rsi_reversion(close),
        "bollinger_breakout": _bollinger_breakout(close),
        "macd_trend": _macd_trend(close),
    }

    results = []
    for name, position in strategies.items():
        metrics = _backtest_positions(close, position)
        score = (
            metrics["total_return"]
            + metrics["sharpe"] * 0.1
            + metrics["max_drawdown"] * 0.5
        )
        results.append(
            {
                "name": name,
                "metrics": metrics,
                "score": round(float(score), 4),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    best = results[0] if results else None

    return {
        "best_strategy": best,
        "strategies": results,
        "lookback_days": int(len(close)),
        "price_column": close_col,
    }
