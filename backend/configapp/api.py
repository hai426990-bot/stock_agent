"""Config API: GET/PUT /api/config, GET /api/config/models.

Single-user: wraps configapp.services.config_bridge (which wraps ConfigManager).
The api_key is NEVER returned in plaintext — GET shows has_api_key: bool.
"""
from typing import Any, Dict, List, Optional

from ninja import Router, Schema

from backend.configapp.services.config_bridge import (
    get_effective_config,
    mask_config,
    save_config,
    get_supported_models,
)

router = Router()


class ConfigOut(Schema):
    api_base: str = ""
    api_key: str = ""           # always "" on read — use has_api_key
    has_api_key: bool = False
    model_name: str = ""
    supported_models: List[str] = []
    llm: Dict[str, Any] = {}
    backtest: Dict[str, Any] = {}
    web: Dict[str, Any] = {}


class ConfigIn(Schema):
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model_name: Optional[str] = None
    supported_models: Optional[List[str]] = None
    llm: Optional[Dict[str, Any]] = None
    backtest: Optional[Dict[str, Any]] = None


class ModelsOut(Schema):
    supported_models: List[str]


@router.get("", response=ConfigOut)
def get_config(request):
    """Return the merged config. api_key is masked (has_api_key flag instead)."""
    return ConfigOut(**mask_config(get_effective_config()))


@router.put("", response=ConfigOut)
def update_config(request, payload: ConfigIn):
    """Update non-secret config (+ optional api_key). Persists to config_user.json."""
    saved = save_config(payload.dict(exclude_none=True))
    return ConfigOut(**saved)


@router.get("/models", response=ModelsOut)
def list_models(request):
    """List supported models for the dropdown."""
    return ModelsOut(supported_models=get_supported_models())
