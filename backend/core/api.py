"""Core API: health check."""
from ninja import Router
from ninja import Schema

router = Router()


class HealthOut(Schema):
    status: str
    version: str


@router.get("/health", response=HealthOut)
def health(request):
    """Liveness probe. Returns 200 if the API is up."""
    return HealthOut(status="ok", version="1.0.0")
