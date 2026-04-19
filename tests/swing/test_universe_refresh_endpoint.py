# tests/swing/test_universe_refresh_endpoint.py
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from api.indicators.swing.pipeline.universe_refresh import run_swing_universe_refresh
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def test_skip_when_deepvue_is_fresh():
    sb = FakeSupabaseClient()
    now = datetime.now(timezone.utc)
    sb.table("swing_universe").insert([{
        "id": 1, "ticker": "NVDA", "source": "deepvue-csv", "batch_id": str(uuid4()),
        "added_at": (now - timedelta(days=2)).isoformat(), "removed_at": None,
    }])
    result = run_swing_universe_refresh(sb)
    assert result["skipped"] is True
    assert "deepvue" in result["skip_reason"].lower()


@patch("api.indicators.swing.pipeline.universe_refresh.generate_backend_universe")
def test_runs_generator_when_universe_stale(mock_gen):
    sb = FakeSupabaseClient()
    mock_gen.return_value = {
        "passers": {"AAPL": {"fundamentals": {"quarterly_revenue_yoy": [0.45]}}},
        "stats": {"base_count": 100, "stage12_count": 50, "stage3_count": 10, "final_count": 1},
    }
    result = run_swing_universe_refresh(sb)
    assert result["skipped"] is False
    assert result["final_count"] == 1
    rows = sb.table("swing_universe").rows
    assert any(r["ticker"] == "AAPL" and r["source"] == "backend-generated" for r in rows)
