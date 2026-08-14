"""WSGI config (used by runserver and gunicorn --bind)."""
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

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
