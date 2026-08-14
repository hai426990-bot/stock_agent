"""Orchestrator + SSE plumbing tests with a FAKE graph.

No real API key / AkShare / LLM needed — orchestrator.get_graph is monkeypatched
to return a fake app whose .stream() yields {node_name: state_update} dicts.

Coverage:
  - build_initial_state key/config completeness
  - _run_graph success path + event persistence + api_key non-leakage
  - _run_graph error path (node error, graph crash, empty stream)
  - stream_events replay / resume_from / done / deleted-report / timeout
"""
import asyncio
from unittest.mock import patch

from django.test import TransactionTestCase

from backend.analysis.models import AnalysisReport, AnalysisNodeEvent
from backend.analysis.services import orchestrator
from backend.analysis.services.state_builder import build_initial_state


class FakeApp:
    """Mimics the compiled LangGraph: app.stream(initial_state) yields
    {node_name: state_update} dicts."""

    def __init__(self, events):
        self.events = events

    def stream(self, initial_state):
        for ev in self.events:
            yield ev


FAKE_EVENTS = [
    {"supervisor": {"messages": ["supervisor done"]}},
    {"news_node": {"news_analysis": "news ok", "sentiment_score": 0.3}},
    {"quant_node": {"quant_data": {"backtest_candidates": []}}},
    {"telegraph_node": {"telegraph_analysis": "telegraph ok"}},
    {"strategy_node": {"strategy_report": "# 报告\n结论：买入"}},
    {"risk_node": {"risk_assessment": "通过", "revision_needed": False}},
]


class OrchestratorTests(TransactionTestCase):
    def setUp(self):
        self.report = AnalysisReport.objects.create(
            query="600519", stock_code="600519", stock_name="贵州茅台",
            is_sector=False, sector_type="", status=AnalysisReport.Status.PENDING,
        )

    def _fake_graph(self, events):
        return patch.object(orchestrator, "get_graph", return_value=FakeApp(events))

    def test_state_builder_produces_full_agentstate(self):
        """state_builder must produce all AgentState keys + the config keys agents read."""
        state = build_initial_state(self.report)
        expected = {
            "stock_code", "stock_name", "is_sector", "sector_type", "sector_cons",
            "news_items", "news_analysis", "sentiment_score", "fear_greed_index",
            "quant_data", "technical_indicators", "backtest_result",
            "strategy_report", "risk_assessment", "messages", "next_node",
            "revision_needed", "human_approval", "count", "is_web_mode",
            "reasoning_content", "config", "error", "consecutive_failures",
        }
        self.assertEqual(expected, set(state.keys()), f"missing: {expected - set(state.keys())}")
        agent_cfg = set(state["config"].keys())
        expected_cfg = {
            "api_key", "api_base", "model_name", "temperature", "max_tokens",
            "thinking_mode", "backtest_lookback_days", "backtest_initial_cash",
            "backtest_sector_days", "backtest_commission", "backtest_slippage",
            "backtest_max_runs",
            "news_rss_urls", "news_enable_reddit", "news_enable_x",
            "news_rss_limit", "news_reddit_limit", "news_x_limit",
        }
        self.assertTrue(expected_cfg.issubset(agent_cfg), f"config missing: {expected_cfg - agent_cfg}")

    def test_run_graph_completes_and_persists_events(self):
        with self._fake_graph(FAKE_EVENTS):
            orchestrator._run_graph(str(self.report.id))

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalysisReport.Status.COMPLETED)
        self.assertEqual(self.report.final_state.get("strategy_report"), "# 报告\n结论：买入")
        self.assertEqual(self.report.final_state.get("risk_assessment"), "通过")
        # api_key must NOT leak into final_state (project_serializable drops config)
        self.assertNotIn("config", self.report.final_state)
        self.assertNotIn("api_key", self.report.final_state)

        events = list(AnalysisNodeEvent.objects.filter(report=self.report).order_by("seq"))
        names = [e.node for e in events]
        self.assertEqual(names, ["supervisor", "news_node", "quant_node", "telegraph_node",
                                 "strategy_node", "risk_node"])
        self.assertTrue(all(e.status == "completed" for e in events))

    def test_stream_events_replays_then_done(self):
        with self._fake_graph(FAKE_EVENTS):
            orchestrator._run_graph(str(self.report.id))

        async def collect():
            out = []
            async for evt in orchestrator.stream_events(str(self.report.id), resume_from=0):
                out.append(evt)
            return out
        events = asyncio.run(collect())

        # 6 node events + 1 done
        self.assertEqual(len(events), 7)
        self.assertEqual(events[0]["event"], "node")
        self.assertEqual(events[0]["node"], "supervisor")
        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(events[-1]["report_id"], str(self.report.id))

    def test_stream_events_resume_from_skips_seen(self):
        with self._fake_graph(FAKE_EVENTS):
            orchestrator._run_graph(str(self.report.id))

        async def collect_from_3():
            out = []
            async for evt in orchestrator.stream_events(str(self.report.id), resume_from=3):
                out.append(evt)
            return out
        resumed = asyncio.run(collect_from_3())
        # seq 4, 5, 6 (3 nodes) + done
        self.assertEqual(len(resumed), 4)
        self.assertEqual(resumed[0]["seq"], 4)

    def test_error_path_marks_failed_and_records_error_event(self):
        with self._fake_graph([
            {"supervisor": {}},
            {"news_node": {"error": "AkShare timeout"}},
        ]):
            report = AnalysisReport.objects.create(
                query="000000", stock_code="000000", stock_name="bad",
                is_sector=False, status=AnalysisReport.Status.PENDING,
            )
            orchestrator._run_graph(str(report.id))
        report.refresh_from_db()
        self.assertEqual(report.status, AnalysisReport.Status.FAILED)
        self.assertIn("AkShare timeout", report.error)
        err_events = AnalysisNodeEvent.objects.filter(report=report, status="error")
        self.assertTrue(err_events.exists())


class OrchestratorEdgeCaseTests(TransactionTestCase):
    def setUp(self):
        self.report = AnalysisReport.objects.create(
            query="600519", stock_code="600519", stock_name="贵州茅台",
            is_sector=False, sector_type="", status=AnalysisReport.Status.PENDING,
        )

    def test_orchestrator_stops_on_first_error(self):
        with patch.object(orchestrator, "get_graph", return_value=FakeApp([
            {"supervisor": {}},
            {"news_node": {"error": "API rate limit exceeded"}},
        ])):
            orchestrator._run_graph(str(self.report.id))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalysisReport.Status.FAILED)
        self.assertIn("API rate limit exceeded", self.report.error)

    def test_orchestrator_handles_graph_crash(self):
        with patch.object(orchestrator, "get_graph", side_effect=RuntimeError("graph compilation failed")):
            orchestrator._run_graph(str(self.report.id))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalysisReport.Status.FAILED)

    def test_orchestrator_handles_empty_stream(self):
        with patch.object(orchestrator, "get_graph", return_value=FakeApp([])):
            orchestrator._run_graph(str(self.report.id))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AnalysisReport.Status.COMPLETED)

    def test_stream_events_after_report_deleted(self):
        with patch.object(orchestrator, "get_graph", return_value=FakeApp([
            {"supervisor": {}},
        ])):
            report_id = str(self.report.id)
            orchestrator._run_graph(report_id)

        # Ensure events were created
        self.assertGreater(AnalysisNodeEvent.objects.filter(report_id=self.report.id).count(), 0)

        async def collect():
            out = []
            async for evt in orchestrator.stream_events(report_id, resume_from=0):
                out.append(evt)
            return out

        self.report.delete()
        events = asyncio.run(collect())
        self.assertTrue(any(e.get("event") == "error" for e in events))

    def test_stream_events_empty_queue_timeout(self):
        """If the queue times out but the DB shows completed, the stream should
        close with a done event."""
        with patch.object(orchestrator, "get_graph", return_value=FakeApp([
            {"supervisor": {}},
            {"news_node": {"news_analysis": "done"}},
        ])):
            orchestrator._run_graph(str(self.report.id))

        async def collect():
            out = []
            async for evt in orchestrator.stream_events(str(self.report.id), resume_from=0):
                out.append(evt)
            return out
        events = asyncio.run(collect())
        self.assertEqual(events[-1]["event"], "done")
