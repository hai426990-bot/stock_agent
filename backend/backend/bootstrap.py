"""Shared UTF-8 console bootstrap for manage.py / asgi.py / wsgi.py.

The core modules (agents/*, tools/*, config.py, logger.py) print emoji/Chinese
on stdout; on Windows consoles this raises GBK codec errors unless the streams
are reconfigured to UTF-8. Each Django entry point must also put PROJECT_ROOT
on sys.path BEFORE importing anything from `backend`, so that part stays inline
in the entry points (it cannot live in an importable helper module).

Only the stream reconfiguration is shared here.
"""
import sys

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent                      # repo root (agents/ etc. live here)


def force_utf8() -> None:
    """Reconfigure stdout/stderr to UTF-8 (Windows console safety)."""
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
