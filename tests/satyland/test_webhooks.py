import os
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from api.main import app


@pytest.mark.asyncio
class TestTradingViewWebhook:
    """TradingView webhook endpoint tests."""

    async def test_missing_token_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/webhooks/tradingview", json={
                "ticker": "SPY", "timeframe": "3", "setup": "flag_into_ribbon",
                "direction": "long", "price": 562.0,
            })
            assert resp.status_code == 422  # missing required query param

    async def test_wrong_token_returns_401(self):
        with patch.dict(os.environ, {"TRADINGVIEW_WEBHOOK_SECRET": "correct_secret"}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/webhooks/tradingview?token=wrong_secret",
                    json={
                        "ticker": "SPY", "timeframe": "3",
                        "setup": "flag_into_ribbon", "direction": "long",
                        "price": 562.0,
                    },
                )
                assert resp.status_code == 401

    async def test_valid_webhook_returns_200(self):
        with patch.dict(os.environ, {"TRADINGVIEW_WEBHOOK_SECRET": "test123"}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/webhooks/tradingview?token=test123",
                    json={
                        "ticker": "SPY", "timeframe": "3",
                        "setup": "flag_into_ribbon", "direction": "long",
                        "price": 562.0, "alert": "test alert",
                    },
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "processed"
                assert data["direction"] == "bullish"

    async def test_invalid_setup_returns_400(self):
        with patch.dict(os.environ, {"TRADINGVIEW_WEBHOOK_SECRET": "test123"}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/webhooks/tradingview?token=test123",
                    json={
                        "ticker": "SPY", "timeframe": "3",
                        "setup": "nonexistent_setup", "direction": "long",
                        "price": 562.0,
                    },
                )
                assert resp.status_code == 400

    async def test_direction_normalization(self):
        with patch.dict(os.environ, {"TRADINGVIEW_WEBHOOK_SECRET": "test123"}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/webhooks/tradingview?token=test123",
                    json={
                        "ticker": "SPY", "timeframe": "3",
                        "setup": "golden_gate", "direction": "short",
                        "price": 558.0,
                    },
                )
                assert resp.status_code == 200
                assert resp.json()["direction"] == "bearish"
