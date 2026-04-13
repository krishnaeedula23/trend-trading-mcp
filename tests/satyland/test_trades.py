import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
class TestTradeEndpoints:
    async def test_create_trade(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "ticker": "SPY",
                "direction": "long",
                "setup_type": "flag_into_ribbon",
                "entry_price": 562.40,
                "stop_price": 561.20,
                "target_price": 564.80,
                "sizing": 5,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["trade"]["ticker"] == "SPY"
            assert data["trade"]["status"] == "open"

    async def test_incomplete_trade(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "ticker": "SPY",
                "direction": "long",
                "setup_type": "flag_into_ribbon",
                "entry_price": 562.40,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["trade"]["status"] == "incomplete"
            assert "stop_price" in data["missing_fields"]

    async def test_invalid_direction(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "ticker": "SPY",
                "direction": "sideways",
                "setup_type": "orb",
            })
            assert resp.status_code == 400

    async def test_invalid_setup_type(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "ticker": "SPY",
                "direction": "long",
                "setup_type": "nonexistent",
            })
            assert resp.status_code == 400

    async def test_list_trades(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/trades")
            assert resp.status_code == 200
            assert "trades" in resp.json()

    async def test_update_trade_empty_body(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch("/api/trades/some-id", json={})
            assert resp.status_code == 400
