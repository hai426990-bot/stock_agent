"""Analysis API: POST (create+start), GET stream (SSE), GET detail, GET list, DELETE.

This is the core of the backend. POST resolves the entity, creates an
AnalysisReport, and kicks off the LangGraph run in a background thread.
GET /{id}/stream is an SSE endpoint that drains orchestrator.stream_events().
"""
import json
from typing import Optional

from django.http import StreamingHttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from backend.analysis.models import AnalysisReport
from backend.analysis.schemas import AnalysisCreateIn, AnalysisCreateOut, AnalysisListItem, AnalysisDetailOut
from backend.analysis.services.entity_resolver import resolve_entity
from backend.analysis.services.orchestrator import (
    start_analysis, stream_events, submit_approval, is_awaiting_approval, _is_valid_uuid,
)
from backend.configapp.services.config_bridge import mask_config, get_effective_config

router = Router()


@router.post("", response={202: AnalysisCreateOut})
def create_analysis(request, payload: AnalysisCreateIn):
    """Create an AnalysisReport, resolve the entity, and start the graph run.

    Returns 202 with the job_id immediately; the client then opens the SSE
    stream at GET /{job_id}/stream.
    """
    try:
        info = resolve_entity(payload.query)
    except ValueError as e:
        return JsonResponse({"detail": str(e)}, status=400)

    report = AnalysisReport.objects.create(
        query=payload.query,
        stock_code=info["stock_code"],
        stock_name=info["stock_name"],
        is_sector=info["is_sector"],
        sector_type=info.get("sector_type", ""),
        sector_cons=info.get("sector_cons", []) or [],
        status=AnalysisReport.Status.PENDING,
        config_snapshot=mask_config(get_effective_config()),
    )
    try:
        start_analysis(report)
    except RuntimeError as e:
        # Worker cap reached: clean up the pending report and tell the client.
        report.delete()
        return JsonResponse({"detail": str(e)}, status=429)
    return JsonResponse(
        {
            "job_id": str(report.id),
            "status": "pending",
            "stock_code": report.stock_code,
            "stock_name": report.stock_name,
            "is_sector": report.is_sector,
        },
        status=202,
    )


@router.get("/{job_id}/stream")
async def analysis_stream(request, job_id: str):
    """Server-Sent Events stream of node-by-node progress.

    Supports Last-Event-ID / ?resume_from=<seq> for reconnect.
    Emits:
        event: node\\ndata: {"seq":N,"node":"...","status":"completed|error","message":"..."}
        event: done\\ndata: {"report_id":"..."}
        event: error\\ndata: {"node":"...","message":"..."}

    Must be an async view: with a sync view Django buffers the whole async
    generator (async_to_sync(to_list)) and the stream arrives only when the
    analysis finishes.
    """
    if not _is_valid_uuid(job_id):
        return JsonResponse({"detail": "invalid job_id"}, status=404)

    resume_from = 0
    last_event_id = request.headers.get("Last-Event-ID")
    if last_event_id:
        try:
            resume_from = int(last_event_id)
        except (TypeError, ValueError):
            resume_from = 0
    qs = request.GET.get("resume_from")
    if qs:
        try:
            resume_from = max(resume_from, int(qs))
        except (TypeError, ValueError):
            pass

    async def event_stream():
        async for evt in stream_events(job_id, resume_from=resume_from):
            event_name = evt.get("event", "node")
            data = {k: v for k, v in evt.items() if k != "event"}
            # include seq as the SSE id so Last-Event-ID works on reconnect
            yield _sse(event_name, data, event_id=evt.get("seq"))

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"  # disable nginx buffering
    resp["Connection"] = "keep-alive"
    return resp


@router.get("/{job_id}", response=AnalysisDetailOut)
def analysis_detail(request, job_id: str):
    """Full AnalysisReport (status + final_state)."""
    if not _is_valid_uuid(job_id):
        raise Http404
    report = get_object_or_404(AnalysisReport, id=job_id)
    return _serialize_detail(report)


class ApprovalIn(Schema):
    approved: bool = True
    comment: str = ""


@router.post("/{job_id}/approval")
def analysis_approval(request, job_id: str, payload: ApprovalIn):
    """Human-in-the-loop: deliver the approval verdict to a paused worker.

    The worker is blocked at the approval gate (report status
    "awaiting_approval"); this wakes it with {"approved", "comment"}.
    Returns 404 for unknown jobs and 409 when nobody is awaiting approval.
    """
    if not _is_valid_uuid(job_id):
        return JsonResponse({"detail": "invalid job_id"}, status=404)
    if not AnalysisReport.objects.filter(id=job_id).exists():
        return JsonResponse({"detail": "report not found"}, status=404)
    if not is_awaiting_approval(job_id):
        return JsonResponse(
            {"detail": "该任务当前不处于等待审批状态"}, status=409,
        )
    submit_approval(job_id, {"approved": payload.approved, "comment": payload.comment or ""})
    return JsonResponse({"message": "approval submitted", "approved": payload.approved})


@router.get("", response=list[AnalysisListItem])
def analysis_list(request, page: int = 1, page_size: int = 20,
                  stock_code: Optional[str] = None, status: Optional[str] = None):
    """Paginated analysis history list (lightweight)."""
    qs = AnalysisReport.objects.all()
    if stock_code:
        qs = qs.filter(stock_code=stock_code)
    if status:
        qs = qs.filter(status=status)
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    total = qs.count()
    start = (page - 1) * page_size
    items = qs[start:start + page_size]
    return [_serialize_list(r) for r in items]


@router.delete("/{job_id}")
def analysis_delete(request, job_id: str):
    """Delete an analysis report (and its node events via cascade)."""
    if not _is_valid_uuid(job_id):
        raise Http404
    AnalysisReport.objects.filter(id=job_id).delete()
    return {"message": "deleted"}


# --- helpers -----------------------------------------------------------------

def _serialize_list(r: AnalysisReport) -> AnalysisListItem:
    return AnalysisListItem(
        id=str(r.id),
        stock_code=r.stock_code,
        stock_name=r.stock_name,
        is_sector=r.is_sector,
        status=r.status,
        error=r.error or "",
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _serialize_detail(r: AnalysisReport) -> AnalysisDetailOut:
    return AnalysisDetailOut(
        id=str(r.id),
        query=r.query or "",
        stock_code=r.stock_code,
        stock_name=r.stock_name,
        is_sector=r.is_sector,
        sector_type=r.sector_type or "",
        status=r.status,
        error=r.error or "",
        final_state=r.final_state or {},
        config_snapshot=r.config_snapshot or {},
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


def _sse(event: str, data: dict, event_id=None) -> str:
    """Format a single SSE message."""
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")  # trailing blank line separates messages
    return "\n".join(lines) + "\n"
