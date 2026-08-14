"""批量回测评估脚本：在多个代表性股票上评估全部注册策略，输出排名。

用法:
    .venv/Scripts/python scripts/benchmark_strategies.py [--days 730] [--stocks 600519,000858] [--top 15]

输出: 控制台排名表 + scripts/benchmark_results.csv
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data import DataManager
from backtest.engine import VectorizedEngine
from backtest.analytics import PerformanceAnalytics
from backtest.strategy import STRATEGY_REGISTRY

DEFAULT_STOCKS = [
    "600519", "000858", "601318", "600036", "300750",
    "002594", "600900", "601899", "000333", "688981",
]


def evaluate_stock(dm: DataManager, engine: VectorizedEngine, symbol: str,
                   start_date: str) -> list:
    df = dm.get_data(symbol, start_date=start_date, add_indicators=True)
    if df.empty:
        print(f"  ⚠️ {symbol}: 无数据")
        return []
    rows = []
    for name, strategy_cls in STRATEGY_REGISTRY.items():
        required = getattr(strategy_cls, "required_columns", []) or []
        if any(c not in df.columns for c in required):
            continue
        grids = getattr(strategy_cls, "param_grid", None) or [None]
        for params in grids:
            try:
                strat = strategy_cls(params=params)
                res = engine.run(strat, df)
                m = PerformanceAnalytics.calculate_metrics(res, initial_cash=engine.initial_cash)
                rows.append({
                    "symbol": symbol,
                    "strategy": name,
                    "params": strat.params.model_dump(),
                    **m,
                })
            except Exception as e:
                print(f"  ⚠️ {symbol}/{name} 失败: {e}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--stocks", default=",".join(DEFAULT_STOCKS))
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    stocks = [s.strip() for s in args.stocks.split(",") if s.strip()]
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    dm = DataManager()
    engine = VectorizedEngine(initial_cash=100000.0, commission=0.0003, slippage=0.001)

    all_rows = []
    for symbol in stocks:
        print(f"📥 回测 {symbol} ...")
        t0 = time.time()
        all_rows.extend(evaluate_stock(dm, engine, symbol, start_date))
        print(f"   完成 ({time.time() - t0:.1f}s)")

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("❌ 无回测结果")
        return
    df["params_str"] = df["params"].apply(lambda d: str(d) if isinstance(d, dict) else str(d))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    # 聚合: 每策略多股票平均
    agg = df.groupby(["strategy", "params_str"]).agg(
        total_return=("total_return", "mean"),
        cagr=("cagr", "mean"),
        sharpe=("sharpe", "mean"),
        calmar=("calmar", "mean"),
        max_drawdown=("max_drawdown", "mean"),
        win_rate=("win_rate", "mean"),
        trade_count=("trade_count", "mean"),
        n_stocks=("symbol", "count"),
    ).reset_index()

    # 综合得分: 兼顾收益与风险调整后表现 (Sharpe 与 Calmar 加权)
    agg["score"] = agg["sharpe"] * 0.5 + agg["calmar"] * 0.5
    agg = agg.sort_values("score", ascending=False)

    # 只看至少 3 只股票有结果的策略（避免单票过拟合）
    agg_robust = agg[agg["n_stocks"] >= 3].head(args.top)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print("\n===== 📊 策略排名 (多股票平均, 至少3只票) =====")
    show = agg_robust.copy()
    print(show.to_string(index=False))
    print(f"\n共评估 {df['strategy'].nunique()} 个策略 × {df['symbol'].nunique()} 只股票 = {len(df)} 个回测")
    print(f"详细结果已保存到 {out}")


if __name__ == "__main__":
    main()
