"""Tests for the core health endpoint."""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthEndpoint:
    def test_health_returns_200(self):
        c = Client()
        resp = c.get("/api/core/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_includes_version(self):
        c = Client()
        resp = c.get("/api/core/health")
        data = resp.json()
        assert "version" in data
