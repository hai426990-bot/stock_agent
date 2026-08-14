"""Shared Pydantic schemas reused across apps."""
from ninja import Schema


class MessageOut(Schema):
    """Generic {message: str} envelope."""
    message: str


class ErrorOut(Schema):
    """Generic error envelope."""
    detail: str
