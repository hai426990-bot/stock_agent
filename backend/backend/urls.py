"""Root URL configuration. Mounts the django-ninja API under /api/ and serves
the built React SPA for all other paths (SPA fallback)."""
from django.contrib import admin
from django.urls import path, re_path
from django.http import FileResponse, HttpResponseNotFound, JsonResponse
from django.conf import settings
from pathlib import Path

from backend.backend.api import api


def spa_fallback(request):
    """Serve index.html for any non-/api/ path so React Router owns client-side
    routing. Only active when the built frontend exists (production)."""
    index = Path(settings.STATIC_ROOT) / "frontend" / "index.html"
    if index.exists():
        return FileResponse(open(index, "rb"))
    return HttpResponseNotFound(
        "Frontend not built. Run `npm run build` in frontend/, or use the Vite "
        "dev server (npm run dev) during development."
    )


def api_fallback(request):
    """Unknown /api/* path -> JSON 404 (instead of the SPA HTML fallback)."""
    return JsonResponse({"detail": "Not Found"}, status=404)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    # Any other /api/* path that django-ninja didn't match -> JSON 404
    re_path(r"^api/.*$", api_fallback),
    # SPA fallback: any path not matched above and not a static file -> index.html
    re_path(r"^.*$", spa_fallback),
]
