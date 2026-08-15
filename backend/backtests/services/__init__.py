"""Backtests service layer: persist backtest runs into Django (BacktestResult).

Web-mode analyses persist each strategy run here (linked to the AnalysisReport);
the CLI keeps using the file-based backtest/persistence.py. The API in
backend/backtests/api.py reads/writes these rows.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from backend.analysis.models import AnalysisReport
from backend.backtests.models import BacktestResult


def record_backtest(report_id: str, strategy_name: str, params: Dict[str, Any],
                    metrics: Dict[str, Any], data_info: Dict[str, Any],
                    engine_info: Optional[Dict[str, Any]] = None) -> Optional[BacktestResult]:
    """Persist one backtest run linked to an AnalysisReport.

    Best-effort: raises nothing (callers run in worker threads; a DB hiccup
    must not kill the analysis). Returns the row, or None on failure.
    """
    try:
        report = AnalysisReport.objects.get(id=report_id) if report_id else None
    except Exception:
        # 无效 UUID / 报告不存在 / DB 异常：放弃入库（worker 线程内 best-effort）
        return None

    run_id = uuid.uuid4().hex[:12]
    return BacktestResult.objects.create(
        run_id=run_id,
        timestamp=datetime.now(),
        strategy_name=strategy_name,
        stock_code=data_info.get("symbol", "UNKNOWN"),
        parameters=params,
        engine=engine_info or {},
        data_info=data_info,
        metrics=metrics,
        sharpe=float(metrics.get("sharpe", 0) or 0),
        cagr=float(metrics.get("cagr", 0) or 0),
        max_drawdown=float(metrics.get("max_drawdown", 0) or 0),
        win_rate=float(metrics.get("win_rate", 0) or 0),
        report=report,
    )
