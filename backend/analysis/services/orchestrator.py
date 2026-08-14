"""orchestrator: the single place that touches graph.create_alpha_flow_graph().

Ports the stream loop from app.py:540-548 / main.py:313-335. Runs the blocking
LangGraph stream in a background thread and publishes per-node progress events
to a stdlib queue.Queue per job_id, which the SSE view drains via asyncio.to_thread.

Every event is ALSO persisted to AnalysisNodeEvent, so:
  - late subscribers / reconnects replay missed events from the DB (Last-Event-ID)
  - if the worker thread dies without flushing the queue, the SSE view detects
    terminal report.status via a DB poll and closes cleanly

Design:
  - start_analysis(report) -> registers a queue.Queue for report.id, kicks off
    _run_graph in a daemon thread, returns immediately.
  - stream_events(report_id, resume_from) -> async generator yielding SSE-ready
    dicts: replays DB events with seq > resume_from, then drains the live queue.

Events yielded have shape:
    {"event": "node", "seq": N, "node": "<name>", "status": "completed|error", ...}
    {"event": "done", "report_id": "<uuid>"}
    {"event": "error", "node": "<name>", "message": "..."}
"""
import asyncio
import queue
import threading
import traceback
import uuid
from asgiref.sync import sync_to_async
from typing import Any, AsyncIterator, Dict, Optional

from backend.analysis.models import AnalysisReport, AnalysisNodeEvent
from backend.analysis.services.state_builder import build_initial_state, project_serializable

# Sentinels pushed onto the queue to signal terminal state.
_DONE = object()
_FAILED = object()

# Per-job stdlib queues (thread-safe, loop-agnostic): job_id (str) -> queue.Queue
_queues: Dict[str, "queue.Queue"] = {}
# RLock: start_analysis acquires it and then calls get_queue(), which acquires
# it again — a plain Lock would self-deadlock every POST.
_lock = threading.RLock()
# Track running jobs so a duplicate POST doesn't double-start.
_running: Dict[str, bool] = {}
# Cap on concurrent analysis workers (AkShare/LLM are IO-heavy; a few parallel
# runs are fine, unbounded threads are not).
MAX_WORKERS = 2

# The compiled LangGraph is static per process — compile it once and reuse
# across analyses instead of rebuilding on every POST.
_graph = None
_graph_lock = threading.Lock()


def get_graph():
    """Return the cached compiled LangGraph (thread-safe lazy singleton)."""
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                from graph import create_alpha_flow_graph
                _graph = create_alpha_flow_graph()
    return _graph


def get_queue(job_id: str) -> "queue.Queue":
    """Get (or create) the queue for a job. The SSE view calls this."""
    with _lock:
        if job_id not in _queues:
            _queues[job_id] = queue.Queue()
        return _queues[job_id]


def _put(job_id: str, item: Any) -> None:
    """Thread-safe put into the job's queue (no-op if the queue was cleaned up)."""
    with _lock:
        q = _queues.get(job_id)
    if q is not None:
        q.put(item)


def _record_event(report: AnalysisReport, seq: int, node: str, status: str,
                  payload: Optional[dict] = None) -> None:
    """Persist a node event for SSE resume. Best-effort."""
    try:
        AnalysisNodeEvent.objects.create(
            report=report, seq=seq, node=node, status=status, payload=payload or {}
        )
    except Exception as e:
        # Never let persistence failures kill the worker; log instead of
        # silently dropping so reconnect gaps are diagnosable.
        print(f"⚠️ 事件持久化失败: {e}")


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _get_report(report_id: str):
    """Fetch an AnalysisReport or None. Wrapped in sync_to_async by callers
    that run in an async context. Invalid UUIDs return None (-> 404/error)."""
    if not _is_valid_uuid(report_id):
        return None
    try:
        return AnalysisReport.objects.get(id=report_id)
    except AnalysisReport.DoesNotExist:
        return None


def _run_graph(report_id: str) -> None:
    """Worker thread entry point. Runs the synchronous LangGraph stream loop.

    Runs OUTSIDE any asyncio loop (plain daemon thread). Publishes events to the
    job's stdlib queue and persists them to the DB.
    """
    from django.db import connection

    report = AnalysisReport.objects.get(id=report_id)
    report.status = AnalysisReport.Status.RUNNING
    report.save(update_fields=["status", "updated_at"])

    seq = 0
    try:
        initial_state = build_initial_state(report)
        app = get_graph()
        final = dict(initial_state)

        for output in app.stream(initial_state):
            # output is {node_name: state_update}
            for node_name, state_update in output.items():
                seq += 1
                if isinstance(state_update, dict):
                    final.update(state_update)

                if final.get("error"):
                    _record_event(report, seq, node_name, "error", {"message": final["error"]})
                    _put(report_id, {
                        "event": "node", "seq": seq, "node": node_name,
                        "status": "error", "message": final["error"],
                    })
                    report.status = AnalysisReport.Status.FAILED
                    report.error = final["error"]
                    report.final_state = project_serializable(final)
                    report.save(update_fields=["status", "error", "final_state", "updated_at"])
                    _put(report_id, _FAILED)
                    connection.close()
                    return
                else:
                    _record_event(report, seq, node_name, "completed")
                    _put(report_id, {
                        "event": "node", "seq": seq, "node": node_name,
                        "status": "completed",
                    })

        # Stream completed successfully
        report.final_state = project_serializable(final)
        report.status = AnalysisReport.Status.COMPLETED
        report.save(update_fields=["final_state", "status", "updated_at"])
        _put(report_id, _DONE)

    except Exception as e:
        tb = traceback.format_exc()
        msg = f"{type(e).__name__}: {e}"
        try:
            report = AnalysisReport.objects.get(id=report_id)
            report.status = AnalysisReport.Status.FAILED
            report.error = msg + "\n" + tb
            report.save(update_fields=["status", "error", "updated_at"])
        except Exception as db_err:
            print(f"⚠️ 无法更新失败状态: {db_err}")
        _record_event(report, seq, "orchestrator", "error", {"message": msg})
        _put(report_id, {"event": "error", "node": "orchestrator", "message": msg})
        _put(report_id, _FAILED)
    finally:
        connection.close()
        with _lock:
            _running.pop(report_id, None)
            # Release the queue so completed jobs don't leak memory. Late SSE
            # subscribers replay from the DB and hit the terminal status path;
            # an active drainer still holds its queue reference.
            _queues.pop(report_id, None)


def start_analysis(report: AnalysisReport) -> None:
    """Kick off the graph run for a report in a background daemon thread.

    Safe to call from a sync or async view. The SSE view should call get_queue()
    before this so the worker can publish immediately; if it doesn't, events are
    still persisted to AnalysisNodeEvent and replayed on subscribe.

    Raises RuntimeError if the global worker cap is already reached.
    """
    rid = str(report.id)
    with _lock:
        if _running.get(rid):
            return  # already running
        if len(_running) >= MAX_WORKERS:
            raise RuntimeError(
                f"并发分析任务已达上限 ({MAX_WORKERS})，请等待当前任务完成后再试"
            )
        _running[rid] = True
        get_queue(rid)  # ensure queue exists
    thread = threading.Thread(target=_run_graph, args=(rid,), daemon=True)
    thread.start()


async def stream_events(report_id: str, resume_from: int = 0) -> AsyncIterator[Dict[str, Any]]:
    """Async generator the SSE view consumes.

    1. Replay persisted AnalysisNodeEvent rows with seq > resume_from (reconnect).
    2. If the report is already terminal, emit done/error and return.
    3. Otherwise drain the live queue (with a timeout) until a sentinel arrives;
       on timeout, poll the DB for terminal status in case the worker died.

    Django ORM calls are wrapped in sync_to_async because this runs in an async
    context (the SSE view is async def); Django blocks sync DB access in async.
    """
    seen_seqs = set()

    # 1. Replay persisted events (sync DB query -> wrap)
    replay_events = await sync_to_async(list)(
        AnalysisNodeEvent.objects.filter(report_id=report_id, seq__gt=resume_from).order_by("seq")
    )
    for ev in replay_events:
        seen_seqs.add(ev.seq)
        if ev.status == AnalysisNodeEvent.Status.ERROR:
            yield {"event": "node", "seq": ev.seq, "node": ev.node,
                   "status": "error", "message": (ev.payload or {}).get("message", "")}
        else:
            yield {"event": "node", "seq": ev.seq, "node": ev.node, "status": "completed"}

    # 2. Check current status
    report = await sync_to_async(_get_report)(report_id)
    if report is None:
        yield {"event": "error", "node": "orchestrator", "message": "report not found"}
        return
    if report.status == AnalysisReport.Status.COMPLETED:
        yield {"event": "done", "report_id": report_id}
        return
    if report.status == AnalysisReport.Status.FAILED:
        yield {"event": "error", "node": "orchestrator", "message": report.error or "analysis failed"}
        return

    # 3. Drain the live queue
    q = get_queue(report_id)
    while True:
        try:
            # Block in a worker thread so the asyncio loop stays responsive.
            item = await asyncio.to_thread(q.get, True, 2.0)
        except queue.Empty:
            # Timeout: check whether the report went terminal (worker may have
            # died before pushing a sentinel).
            report = await sync_to_async(_get_report)(report_id)
            if report is None:
                yield {"event": "error", "node": "orchestrator", "message": "report not found"}
                break
            if report.status == AnalysisReport.Status.COMPLETED:
                yield {"event": "done", "report_id": report_id}
                break
            if report.status == AnalysisReport.Status.FAILED:
                yield {"event": "error", "node": "orchestrator",
                       "message": report.error or "analysis failed"}
                break
            # Worker died without marking the report terminal (e.g. DB write
            # failed inside the exception path): nothing will ever arrive.
            with _lock:
                worker_alive = _running.get(report_id, False)
            if not worker_alive:
                yield {"event": "error", "node": "orchestrator",
                       "message": "分析任务异常终止（worker 已退出）"}
                break
            continue  # still running, keep waiting

        if item is _DONE:
            yield {"event": "done", "report_id": report_id}
            break
        if item is _FAILED:
            # The error dict was already yielded before _FAILED; just stop.
            break
        if isinstance(item, dict):
            seq = item.get("seq")
            if seq and seq in seen_seqs:
                continue  # don't duplicate a replayed event
            if seq:
                seen_seqs.add(seq)
            yield item

    # Cleanup the queue
    with _lock:
        _queues.pop(report_id, None)
