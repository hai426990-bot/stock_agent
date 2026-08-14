"""BacktestResult model — replaces .backtest_results/backtest_history.db.

Mirrors the schema of backtest/persistence.py (run_id, timestamp, strategy_name,
stock_code, sharpe/cagr/max_drawdown/win_rate denormalized) plus the full
parameters/engine/data_info/metrics JSON blobs from the sidecar files.
"""
from django.db import models


class BacktestResult(models.Model):
    run_id = models.CharField(max_length=16, unique=True, db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    strategy_name = models.CharField(max_length=128, db_index=True)
    stock_code = models.CharField(max_length=32, db_index=True)

    parameters = models.JSONField(default=dict)
    engine = models.JSONField(default=dict)
    data_info = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)  # sharpe, cagr, max_drawdown, win_rate, ...

    # Denormalized from metrics for filtering/sorting (mirrors old SQLite schema)
    sharpe = models.FloatField(default=0)
    cagr = models.FloatField(default=0)
    max_drawdown = models.FloatField(default=0)
    win_rate = models.FloatField(default=0)

    # Link to the analysis run that produced this backtest, if any
    report = models.ForeignKey(
        "analysis.AnalysisReport",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backtests",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.strategy_name} {self.stock_code} {self.run_id}"
