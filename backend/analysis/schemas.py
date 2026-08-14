"""Pydantic schemas for the analysis API."""
from typing import Any, Dict, List, Optional
from uuid import UUID

from ninja import Schema


class AnalysisCreateIn(Schema):
    query: str  # stock code (6 digits), stock name, or board/sector name


class AnalysisCreateOut(Schema):
    job_id: str
    status: str
    stock_code: str
    stock_name: str
    is_sector: bool


class NodeEventOut(Schema):
    seq: int
    node: str
    status: str
    message: Optional[str] = None


class AnalysisListItem(Schema):
    id: str
    stock_code: str
    stock_name: str
    is_sector: bool
    status: str
    error: str = ""
    created_at: str
    updated_at: str


class AnalysisDetailOut(Schema):
    id: str
    query: str = ""
    stock_code: str
    stock_name: str
    is_sector: bool
    sector_type: str = ""
    status: str
    error: str = ""
    final_state: Dict[str, Any] = {}
    config_snapshot: Dict[str, Any] = {}
    created_at: str
    updated_at: str
