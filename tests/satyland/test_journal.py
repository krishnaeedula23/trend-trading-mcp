import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
class TestJournalEndpoints:
    async def test_create_journal(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/journal", json={
                "date": "2026-04-12",
                "emotional_state": "calm",
                "what_worked": "Waited for confirmation",
                "what_didnt": "Took a revenge trade",
                "lessons": "Stick to the plan",
                "followed_rules": False,
                "rules_broken": ["no revenge trades"],
                "session_grade": "C",
                "total_trades": 3,
                "total_pnl": -150.0,
                "total_r": -1.5,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "journal" in data
            assert data["journal"]["date"] == "2026-04-12"
            assert data["journal"]["emotional_state"] == "calm"
            assert data["journal"]["total_trades"] == 3

    async def test_get_journal(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/journal", params={"date": "2026-04-12"})
            assert resp.status_code == 200
            data = resp.json()
            assert "journal" in data
            assert data["date"] == "2026-04-12"

    async def test_get_journal_defaults_to_today(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/journal")
            assert resp.status_code == 200
            data = resp.json()
            assert "journal" in data
            assert "date" in data

    async def test_create_note(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/notes", json={
                "content": "SPY broke above VWAP with volume — watching for flag into ribbon",
                "ticker": "SPY",
                "category": "setup",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "note" in data
            assert data["note"]["content"].startswith("SPY broke")
            assert data["note"]["category"] == "setup"
            assert data["note"]["ticker"] == "SPY"

    async def test_create_note_auto_category_emotional(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/notes", json={
                "content": "Feeling anxious after the loss — need to reset",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["note"]["category"] == "emotional"

    async def test_create_note_auto_category_lesson(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/notes", json={
                "content": "Learned I should have waited for the ribbon to curl before entering",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["note"]["category"] == "lesson"

    async def test_list_notes(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/notes")
            assert resp.status_code == 200
            data = resp.json()
            assert "notes" in data
            assert isinstance(data["notes"], list)

    async def test_list_notes_by_date(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/notes", params={"date": "2026-04-12"})
            assert resp.status_code == 200
            data = resp.json()
            assert "notes" in data
