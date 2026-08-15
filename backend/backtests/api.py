"""Backtests API — list/get/delete over BacktestResult (Django-persisted history).

Web-mode analyses persist each strategy run via backend/backtests/services
(record_backtest); this router exposes that history. The CLI-only file/sqlite
index from backtest/persistence.py is intentionally NOT exposed here (it is a
single-user cache; the Django rows are the queryable history).
"""
from typing import Optional

from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from backend.backtests.models import BacktestResult
from backend.common.pagination import paginate

router = Router()


class BacktestListOut(Schema):
    id: str
    run_id: str
    strategy_name: str
    stock_code: str
    sharpe: float
    cagr: float
    max_drawdown: float
    win_rate: float
    report_id: Optional[str] = None
    timestamp: str


class BacktestDetailOut(BacktestListOut):
    parameters: dict
    engine: dict
    data_info: dict
    metrics: dict


class BacktestPageOut(Schema):
    items: list[BacktestListOut]
    total: int
    page: int
    page_size: int


@router.get("", response=BacktestPageOut)
def backtest_list(request, page: int = 1, page_size: int = 20,
                  strategy_name: Optional[str] = None,
                  stock_code: Optional[str] = None,
                  report_id: Optional[str] = None):
    """Paginated backtest history (lightweight rows, no JSON blobs)."""
    qs = BacktestResult.objects.all()
    if strategy_name:
        qs = qs.filter(strategy_name=strategy_name)
    if stock_code:
        qs = qs.filter(stock_code=stock_code)
    if report_id:
        qs = qs.filter(report_id=report_id)
    items, total, page, page_size = paginate(qs, page=page, page_size=page_size)
    return BacktestPageOut(
        items=[_serialize_list(r) for r in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{run_id}", response=BacktestDetailOut)
def backtest_detail(request, run_id: str):
    """Full record incl. parameters / engine / data_info / metrics JSON."""
    record = get_object_or_404(BacktestResult, run_id=run_id)
    return _serialize_detail(record)


@router.delete("/{run_id}")
def backtest_delete(request, run_id: str):
    """Delete a record from the history."""
    deleted, _ = BacktestResult.objects.filter(run_id=run_id).delete()
    if not deleted:
        raise get_object_or_404(BacktestResult, run_id=run_id)
    return {"message": "deleted"}


# --- helpers -----------------------------------------------------------------

def _serialize_list(r: BacktestResult) -> BacktestListOut:
    return BacktestListOut(
        id=str(r.id),
        run_id=r.run_id,
        strategy_name=r.strategy_name,
        stock_code=r.stock_code,
        sharpe=r.sharpe,
        cagr=r.cagr,
        max_drawdown=r.max_drawdown,
        win_rate=r.win_rate,
        report_id=str(r.report_id) if r.report_id else None,
        timestamp=r.timestamp.isoformat() if r.timestamp else "",
    )


def _serialize_detail(r: BacktestResult) -> BacktestDetailOut:
    base = _serialize_list(r)
    return BacktestDetailOut(
        **base.dict(),
        parameters=r.parameters or {},
        engine=r.engine or {},
        data_info=r.data_info or {},
        metrics=r.metrics or {},
    )
