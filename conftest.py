"""Root conftest: ensures project dirs are on sys.path before any test runs."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

# PROJECT_ROOT first so that `backend` resolves to the outer namespace package
# (not to the inner backend/backend/ regular package).
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.append(p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings")
