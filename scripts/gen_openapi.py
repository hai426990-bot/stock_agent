"""Dump the django-ninja OpenAPI schema to frontend/src/types/openapi.json.

Used to keep the frontend's generated API types (api.generated.ts, produced by
openapi-typescript) in sync with the backend contracts. CI regenerates both
files and fails on diff (see .github/workflows/ci.yml).

Run from the repo root:
    .venv/Scripts/python scripts/gen_openapi.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Make `backend` (outer namespace package) and the core modules importable
# without Django's manage.py bootstrap. ROOT must come BEFORE ROOT/backend in
# sys.path, otherwise `backend` resolves to the inner backend/backend package.
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.append(p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backend.settings")

import django  # noqa: E402

django.setup()

from backend.backend.api import api  # noqa: E402

schema = api.get_openapi_schema()

out = ROOT / "frontend" / "src" / "types" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(schema, f, ensure_ascii=False, indent=2)

print(f"OpenAPI schema written to {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
