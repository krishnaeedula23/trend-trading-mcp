import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
class TestAnalyticsEndpoints:
    async def test_daily_summary(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/analytics/daily")
            assert resp.status_code == 200
            assert "total_trades" in resp.json() or "error" in resp.json()

    async def test_setup_performance(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/analytics/setup-performance")
            assert resp.status_code == 200
            assert "breakdown" in resp.json()

    async def test_win_rates(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/analytics/win-rates")
            assert resp.status_code == 200
            assert "win_rates" in resp.json()

    async def test_weekly_summary(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/analytics/weekly")
            assert resp.status_code == 200
