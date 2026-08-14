"""Tests for the config API endpoint."""
from unittest.mock import patch

import pytest
from django.test import Client


MOCK_CONFIG = {
    "api_base": "https://api.openai.com/v1",
    "api_key": "sk-1234567890abcdef",
    "model_name": "gpt-4o",
    "supported_models": ["gpt-4o", "gpt-4-turbo"],
    "llm": {"temperature": 0.3, "max_tokens": 8192, "thinking_mode": True},
    "backtest": {"days": 365, "cash": 100000.0},
    "web": {"page_title": "AlphaFlow"},
}


@pytest.mark.django_db
class TestConfigAPI:
    @patch("backend.configapp.api.get_effective_config")
    @patch("backend.configapp.api.mask_config")
    def test_get_config_returns_masked(self, mock_mask, mock_get):
        mock_get.return_value = MOCK_CONFIG
        mock_mask.return_value = {
            "api_base": "https://api.openai.com/v1",
            "api_key": "",
            "has_api_key": True,
            "model_name": "gpt-4o",
            "supported_models": ["gpt-4o", "gpt-4-turbo"],
            "llm": {"temperature": 0.3, "max_tokens": 8192, "thinking_mode": True},
            "backtest": {"days": 365, "cash": 100000.0},
            "web": {"page_title": "AlphaFlow"},
        }
        c = Client()
        resp = c.get("/api/config/")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" not in data or data["api_key"] == ""
        assert data["has_api_key"] is True
        assert data["model_name"] == "gpt-4o"

    @patch("backend.configapp.api.save_config")
    @patch("backend.configapp.api.mask_config")
    @patch("backend.configapp.api.get_effective_config")
    def test_put_config_updates(self, mock_get, mock_mask, mock_save):
        mock_save.return_value = {
            "model_name": "gpt-4-turbo",
            "llm": {"temperature": 0.5},
        }
        mock_mask.return_value = {
            "api_base": "",
            "api_key": "",
            "has_api_key": False,
            "model_name": "gpt-4-turbo",
            "supported_models": [],
            "llm": {"temperature": 0.5},
            "backtest": {},
            "web": {},
        }
        mock_get.return_value = {}

        c = Client()
        resp = c.put("/api/config/", {"model_name": "gpt-4-turbo"}, content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "gpt-4-turbo"
