import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
class TestScheduledEndpoints:
    async def test_morning_brief(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/scheduled/morning-brief")
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data
            assert "MORNING BRIEF" in data["message"] or "Morning Brief" in data["message"]

    async def test_orb_marker(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/scheduled/orb-marker")
            assert resp.status_code == 200
            assert "ORB" in resp.json()["message"]

    async def test_trend_time(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/scheduled/trend-time")
            assert resp.status_code == 200
            assert "Trend Time" in resp.json()["message"]

    async def test_journal_prompt(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/scheduled/journal-prompt")
            assert resp.status_code == 200
            assert "Journal" in resp.json()["message"]

    async def test_all_endpoints_return_200(self):
        """All scheduled endpoints should return 200 even without Slack configured."""
        endpoints = [
            "/api/scheduled/morning-brief",
            "/api/scheduled/orb-marker",
            "/api/scheduled/trend-time",
            "/api/scheduled/euro-close",
            "/api/scheduled/midday-nudge",
            "/api/scheduled/journal-prompt",
            "/api/scheduled/next-day-prep",
            "/api/scheduled/weekly-review",
        ]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for endpoint in endpoints:
                resp = await client.post(endpoint)
                assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"
