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


@pytest.mark.django_db(transaction=True)
class TestApprovalFullStack:
    """真实图 + 编排层 + API 的全链路人工审批集成测试。

    不 mock 图：真 graph（MemorySaver checkpointer + interrupt）在 worker 线程
    中运行，走到 approval_gate 后挂起；测试通过 POST approval 端点恢复，
    断言最终 COMPLETED 且报告已生成。
    """

    def _start_and_wait_status(self, report, target, timeout=15.0):
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            report.refresh_from_db()
            if report.status == target:
                return True
            time.sleep(0.05)
        return False

    def test_full_approval_flow_approve(self):
        import numpy as np
        import pandas as pd
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from backend.analysis.models import AnalysisNodeEvent
        from backend.analysis.services import orchestrator

        rng = np.random.default_rng(7)
        idx = pd.date_range("2025-01-01", periods=300, freq="B")
        close = 100 * (1 + np.linspace(0, 0.25, 300)) + rng.normal(0, 0.5, 300)
        df = pd.DataFrame({
            "dt": idx, "open": close * 0.99, "high": close * 1.01,
            "low": close * 0.98, "close": close, "volume": 2_000_000,
            "adj_close": close, "turnover": 1.0,
        })

        class _FakeChat(BaseChatModel):
            """prompt 内容分发的假 LLM（strategy 使用 prompt | llm 管道）。"""

            risk_calls: int = 0

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                text = "\n".join(str(getattr(m, "content", "")) for m in messages)
                if "首席风险官" in text:
                    self.risk_calls += 1
                    content = '{"decision": "通过", "reason": "逻辑自洽"}'
                elif "资讯侦察兵" in text:
                    content = (
                        '{"analysis": "业绩超预期，行业景气度持续提升，机构上调盈利预测，'
                        '估值处于合理区间，中短期预期差偏正面", "sentiment_score": 0.6, '
                        '"fear_greed_index": 70}'
                    )
                elif "市场动态分析师" in text:
                    content = (
                        '{"event_type": "政策", "impact": "正面", "sentiment": "乐观", '
                        '"comment": "政策利好行业", "opportunities": [], "risks": []}'
                    )
                else:
                    content = "# 投资建议报告\n## 一、核心评级\n买入\n审批集成测试通过"
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=content))]
                )

            @property
            def _llm_type(self):
                return "fake-chat"

        report = AnalysisReport.objects.create(
            query="600519", stock_code="600519", stock_name="贵州茅台",
            is_sector=False, status=AnalysisReport.Status.PENDING,
        )

        llm = _FakeChat()
        with patch("agents.news_agent.build_llm", return_value=llm), \
             patch("agents.strategy_agent.build_llm", return_value=llm), \
             patch("agents.risk_agent.build_llm", return_value=llm), \
             patch("agents.telegraph_agent.build_llm", return_value=llm), \
             patch("agents.news_agent.get_stock_news",
                   return_value=[{"time": "t", "title": "x", "content": "y"}]), \
             patch("agents.news_agent.get_stock_report", return_value=[]), \
             patch("agents.telegraph_agent.get_10jqka_news",
                   return_value=[{"time": "t", "title": "政策", "content": "利好"}]), \
             patch("backtest.data.DataManager.get_data", return_value=df), \
             patch("backtest.persistence.BacktestPersistence.save_result", return_value=""), \
             patch("agents.quant_agent._fetch_financials", return_value={"roe": 0.3}), \
             patch("agents.quant_agent._fetch_fund_flow", return_value={}), \
             patch("agents.quant_agent._fetch_industry_data", return_value={}), \
             patch("agents.quant_agent._fetch_valuation_history", return_value={}), \
             patch("agents.quant_agent._fetch_market_sentiment", return_value={}), \
             patch("backend.analysis.services.state_builder.build_agent_config",
                   return_value={
                       "api_key": "test-key", "api_base": "https://x/v1",
                       "model_name": "gpt-4o", "temperature": 0.5, "max_tokens": 4096,
                       "thinking_mode": False,
                       "backtest_lookback_days": 365, "backtest_initial_cash": 100000.0,
                       "backtest_sector_days": 252, "backtest_commission": 0.0003,
                       "backtest_slippage": 0.001, "backtest_max_runs": 4,
                       "news_rss_urls": "", "news_enable_reddit": False,
                       "news_enable_x": False, "news_rss_limit": 12,
                       "news_reddit_limit": 12, "news_x_limit": 12,
                       "human_approval_enabled": True,
                       "human_approval_timeout": 600,
                       "human_approval_max_rejections": 3,
                   }):
            orchestrator.start_analysis(report)
            assert self._start_and_wait_status(report, AnalysisReport.Status.AWAITING_APPROVAL), \
                f"未进入等待审批状态: {report.status}"

            c = Client()
            resp = c.post(f"/api/analysis/{report.id}/approval",
                          {"approved": True, "comment": "同意"},
                          content_type="application/json")
            assert resp.status_code == 200

            assert self._start_and_wait_status(report, AnalysisReport.Status.COMPLETED), \
                f"审批后未完成: {report.status}"

        report.refresh_from_db()
        assert report.status == AnalysisReport.Status.COMPLETED
        assert "审批集成测试通过" in report.final_state["strategy_report"]
        assert llm.risk_calls == 1  # 审批通过不触发修订
        events = list(AnalysisNodeEvent.objects.filter(report=report).order_by("seq"))
        assert ("approval_gate", "waiting") in [(e.node, e.status) for e in events]
