#!/usr/bin/env python
"""Django management entry point for the AlphaFlow backend."""
import os
import sys
from pathlib import Path

# PROJECT_ROOT must be on sys.path BEFORE importing anything from `backend` so
# the existing core modules (agents, tools, backtest, graph, state, config) are
# importable as top-level packages.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.backend.bootstrap import force_utf8  # noqa: E402

force_utf8()


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
