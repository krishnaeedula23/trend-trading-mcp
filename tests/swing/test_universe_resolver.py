# tests/swing/test_universe_resolver.py
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from api.indicators.swing.universe.resolver import resolve_universe, save_universe_batch
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def test_resolve_uses_fresh_deepvue():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    batch = str(uuid4())
    sb.table("swing_universe").insert([
        {"id": 1, "ticker": "AAPL", "source": "deepvue-csv", "batch_id": batch,
         "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None, "extras": {}},
        {"id": 2, "ticker": "NVDA", "source": "deepvue-csv", "batch_id": batch,
         "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None, "extras": {}},
    ])
    result = resolve_universe(sb)
    assert result.source == "deepvue"
    assert set(result.tickers) == {"AAPL", "NVDA"}


def test_resolve_falls_back_to_backend_when_deepvue_stale():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(days=10)).isoformat()
    fresh = (now - timedelta(days=2)).isoformat()
    sb.table("swing_universe").insert([
        {"id": 1, "ticker": "AAPL", "source": "deepvue-csv", "batch_id": str(uuid4()),
         "added_at": stale, "removed_at": None, "extras": {}},
        {"id": 2, "ticker": "MSFT", "source": "backend-generated", "batch_id": str(uuid4()),
         "added_at": fresh, "removed_at": None, "extras": {}},
    ])
    result = resolve_universe(sb)
    assert result.source == "backend-stale-deepvue"
    assert "MSFT" in result.tickers
