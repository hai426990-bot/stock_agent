"""Top-level django-ninja API. Each app contributes a router; they are mounted
here under /api/<app>/."""
from ninja import NinjaAPI

api = NinjaAPI(
    title="AlphaFlow API",
    description="Django backend for the AlphaFlow stock-analysis platform.",
    version="1.0.0",
    # Single-user personal tool: no auth. (If multi-user is ever needed, add a
    # django-ninja auth= parameter here and a bearer/session dependency.)
)

# Routers are imported and mounted lazily to avoid import cycles at Django startup.
from backend.core.api import router as core_router  # noqa: E402
from backend.configapp.api import router as config_router  # noqa: E402
from backend.market.api import router as market_router  # noqa: E402
from backend.analysis.api import router as analysis_router  # noqa: E402
from backend.backtests.api import router as backtests_router  # noqa: E402

api.add_router("/core/", core_router)
api.add_router("/config/", config_router)
api.add_router("/market/", market_router)
api.add_router("/analysis/", analysis_router)
api.add_router("/backtests/", backtests_router)
