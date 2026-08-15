"""Tests for the analysis API (POST / create, GET stream, detail, list, delete).

Uses TransactionTestCase (or pytest-django transactional_db) because the
orchestrator spawns threads that write to the DB.
"""
from unittest.mock import patch

import pytest
from django.test import Client
from backend.analysis.models import AnalysisReport


@pytest.mark.django_db(transaction=True)
class TestAnalysisCreate:
    def test_create_returns_202(self):
        with patch("backend.analysis.api.resolve_entity") as mock_resolve:
            mock_resolve.return_value = {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "is_sector": False,
                "sector_type": "",
                "sector_cons": [],
            }
            with patch("backend.analysis.api.start_analysis"):
                c = Client()
                resp = c.post("/api/analysis/", {"query": "600519"}, content_type="application/json")
                assert resp.status_code == 202
                data = resp.json()
                assert "job_id" in data
                assert data["stock_code"] == "600519"

    def test_create_invalid_query_returns_400(self):
        with patch("backend.analysis.api.resolve_entity") as mock_resolve:
            mock_resolve.side_effect = ValueError("未找到: ZZZZ")
            c = Client()
            resp = c.post("/api/analysis/", {"query": "ZZZZ"}, content_type="application/json")
            assert resp.status_code == 400

    def test_create_missing_query_returns_422(self):
        c = Client()
        resp = c.post("/api/analysis/", {}, content_type="application/json")
        assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
class TestAnalysisList:
    def test_list_returns_paginated(self):
        AnalysisReport.objects.create(
            stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.COMPLETED,
        )
        c = Client()
        resp = c.get("/api/analysis/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_filters_by_status(self):
        AnalysisReport.objects.create(
            stock_code="000001", stock_name="平安银行",
            is_sector=False, status=AnalysisReport.Status.FAILED,
        )
        c = Client()
        resp = c.get("/api/analysis/", {"status": "failed"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "failed" for r in data)


@pytest.mark.django_db(transaction=True)
class TestAnalysisDelete:
    def test_delete_removes_report(self):
        report = AnalysisReport.objects.create(
            stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.COMPLETED,
        )
        c = Client()
        resp = c.delete(f"/api/analysis/{report.id}")
        assert resp.status_code == 200
        assert AnalysisReport.objects.filter(id=report.id).count() == 0

    def test_delete_nonexistent_is_idempotent(self):
        c = Client()
        resp = c.delete("/api/analysis/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 200


class _FakeApp:
    """Mimics the compiled LangGraph for SSE endpoint tests."""

    def __init__(self, events):
        self.events = events

    def stream(self, initial_state, config=None):
        for ev in self.events:
            yield ev


@pytest.mark.django_db(transaction=True)
class TestAnalysisStream:
    def test_stream_invalid_uuid_returns_404(self):
        c = Client()
        resp = c.get("/api/analysis/not-a-uuid/stream")
        assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
class TestAnalysisStreamASGI:
    """SSE streaming must be tested through the ASGI stack (the sync Django
    test client cannot drain an async StreamingHttpResponse generator)."""

    @pytest.mark.anyio
    async def test_stream_delivers_node_events_and_done(self):
        import time
        import httpx
        from asgiref.sync import sync_to_async
        from backend.backend.asgi import application
        from backend.analysis.services import orchestrator

        report = await sync_to_async(AnalysisReport.objects.create)(
            query="600519", stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.PENDING,
        )
        fake = _FakeApp([
            {"supervisor": {"messages": ["go"]}},
            {"risk_node": {"risk_assessment": "通过", "revision_needed": False}},
        ])

        def _start_and_wait():
            from backend.analysis.api import start_analysis
            # The worker is a separate thread; keep the get_graph patch active
            # until it reaches a terminal state so the real graph never runs.
            with patch.object(orchestrator, "get_graph", return_value=fake):
                start_analysis(report)
                for _ in range(100):
                    report.refresh_from_db()
                    if report.status in (AnalysisReport.Status.COMPLETED,
                                         AnalysisReport.Status.FAILED):
                        break
                    time.sleep(0.05)

        await sync_to_async(_start_and_wait)()
        assert report.status == AnalysisReport.Status.COMPLETED

        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(f"/api/analysis/{report.id}/stream")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        assert "event: node" in body
        assert "supervisor" in body
        assert "event: done" in body

    @pytest.mark.anyio
    async def test_stream_missing_report_returns_error_event(self):
        import httpx
        from backend.backend.asgi import application

        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/analysis/00000000-0000-0000-0000-000000000000/stream")

        assert "error" in resp.text


@pytest.mark.django_db(transaction=True)
class TestAnalysisDetail:
    def test_detail_returns_final_state(self):
        report = AnalysisReport.objects.create(
            query="600519", stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.COMPLETED,
            final_state={"strategy_report": "# 报告"},
        )
        c = Client()
        resp = c.get(f"/api/analysis/{report.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["final_state"]["strategy_report"] == "# 报告"

    def test_detail_invalid_uuid_returns_404(self):
        c = Client()
        resp = c.get("/api/analysis/not-a-uuid")
        assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
class TestAnalysisApproval:
    """POST /api/analysis/{id}/approval — human-in-the-loop verdict delivery."""

    def test_approval_invalid_uuid_returns_404(self):
        c = Client()
        resp = c.post("/api/analysis/not-a-uuid/approval", {"approved": True},
                      content_type="application/json")
        assert resp.status_code == 404

    def test_approval_unknown_report_returns_404(self):
        c = Client()
        resp = c.post("/api/analysis/00000000-0000-0000-0000-000000000000/approval",
                      {"approved": True}, content_type="application/json")
        assert resp.status_code == 404

    def test_approval_not_awaiting_returns_409(self):
        report = AnalysisReport.objects.create(
            stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.RUNNING,
        )
        c = Client()
        resp = c.post(f"/api/analysis/{report.id}/approval", {"approved": True},
                      content_type="application/json")
        assert resp.status_code == 409

    def test_approval_awaiting_submits_verdict(self):
        report = AnalysisReport.objects.create(
            stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.AWAITING_APPROVAL,
        )
        with patch("backend.analysis.api.submit_approval", return_value=True) as mock_submit, \
             patch("backend.analysis.api.is_awaiting_approval", return_value=True):
            c = Client()
            resp = c.post(f"/api/analysis/{report.id}/approval",
                          {"approved": False, "comment": "风险提示不足"},
                          content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is False
        mock_submit.assert_called_once_with(
            str(report.id), {"approved": False, "comment": "风险提示不足"})
