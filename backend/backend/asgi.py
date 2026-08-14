"""ASGI config — async-capable so SSE streaming views (async def) work under
uvicorn. The blocking LangGraph stream loop runs in asyncio.to_thread so the
event loop stays responsive."""
import os
import sys
from pathlib import Path

# sys.path setup must precede any `backend` import (see backend/backend/bootstrap.py)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.backend.bootstrap import force_utf8  # noqa: E402

force_utf8()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
