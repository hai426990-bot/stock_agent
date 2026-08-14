"""Tests for the market dashboard API endpoints.

Uses Django test client. Market endpoints rely on AkShare which requires
network access — we mock the market_service functions to avoid real calls.
"""
from unittest.mock import patch

import pytest
from django.test import Client


@pytest.mark.django_db
class TestMarketIndices:
    def test_indices_returns_list_when_data_exists(self):
        mock_data = [
            {"name": "上证指数", "price": 3200, "change_pct": 0.5},
            {"name": "深证成指", "price": 10000, "change_pct": -0.3},
        ]
        with patch("backend.market.api.get_market_indices", return_value=mock_data):
            c = Client()
            resp = c.get("/api/market/indices")
            assert resp.status_code == 200
            body = resp.json()
            assert "indices" in body
            assert len(body["indices"]) == 2

    def test_indices_handles_exception_gracefully(self):
        with patch("backend.market.api.get_market_indices", side_effect=Exception("timeout")):
            c = Client()
            resp = c.get("/api/market/indices")
            assert resp.status_code == 200
            body = resp.json()
            assert "error" in body


@pytest.mark.django_db
class TestMarketHotSectors:
    def test_hot_sectors_returns_data(self):
        mock_sectors = [
            {"板块名称": "半导体", "涨跌幅": 3.5, "领涨股票": "中芯国际"},
        ]
        with patch("backend.market.api.get_market_hot_sectors", return_value=mock_sectors):
            c = Client()
            resp = c.get("/api/market/hot-sectors?limit=5")
            assert resp.status_code == 200
            body = resp.json()
            assert "sectors" in body

    def test_hot_sectors_handles_empty(self):
        with patch("backend.market.api.get_market_hot_sectors", return_value=[]):
            c = Client()
            resp = c.get("/api/market/hot-sectors")
            assert resp.status_code == 200
            body = resp.json()
            assert body["sectors"] == []


@pytest.mark.django_db
class TestMarketSearch:
    def test_search_stock_code(self):
        with patch("backend.market.api.search") as mock_search:
            mock_search.return_value = {
                "type": "stock",
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "is_sector": False,
                "sector_type": "",
                "sector_cons": [],
            }
            c = Client()
            resp = c.get("/api/market/search", {"q": "600519"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["stock_code"] == "600519"
            assert data["stock_name"] == "贵州茅台"
            assert data["is_sector"] is False

    def test_search_returns_error_for_garbage(self):
        with patch("backend.market.api.search") as mock_search:
            mock_search.side_effect = ValueError("未找到")
            c = Client()
            resp = c.get("/api/market/search", {"q": "ZZZZZZ"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["type"] == "error"
