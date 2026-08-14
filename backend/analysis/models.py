"""Analysis app models: AnalysisReport (replaces analysis_history/*.json) and
AnalysisNodeEvent (enables SSE resume after reconnect)."""
import uuid

from django.db import models


class AnalysisReport(models.Model):
    """One stock/sector analysis run. id is the job_id returned by POST /api/analysis/."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_code = models.CharField(max_length=32, db_index=True)
    stock_name = models.CharField(max_length=128, default="")
    is_sector = models.BooleanField(default=False)
    sector_type = models.CharField(max_length=16, default="", blank=True)
    # Board constituents resolved at POST time; consumed by build_initial_state
    # so sector analyses get the constituent context the strategy agent expects.
    sector_cons = models.JSONField(default=list)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    # Full AgentState snapshot of the decision + data layers
    # (strategy_report, risk_assessment, quant_data, technical_indicators,
    #  sentiment_score, fear_greed_index, news_analysis, telegraph_analysis, ...)
    final_state = models.JSONField(default=dict)
    error = models.TextField(default="", blank=True)
    # Non-secret config snapshot used at run time (model, temperature, backtest params)
    config_snapshot = models.JSONField(default=dict)
    query = models.CharField(max_length=256, default="", blank=True)  # original user query

    # Idempotent legacy import (analysis_history/*.json filename)
    legacy_filename = models.CharField(max_length=128, null=True, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stock_name}({self.stock_code}) {self.status}"


class AnalysisNodeEvent(models.Model):
    """Per-node progress events. Lets SSE resume after reconnect by replaying
    from the Last-Event-ID / seq."""

    class Status(models.TextChoices):
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        ERROR = "error", "Error"

    report = models.ForeignKey(
        AnalysisReport, related_name="events", on_delete=models.CASCADE
    )
    seq = models.PositiveIntegerField()
    node = models.CharField(max_length=32)  # supervisor/news_node/quant_node/...
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("report", "seq"),)
        ordering = ["seq"]

    def __str__(self):
        return f"{self.report_id}#{self.seq} {self.node} {self.status}"
