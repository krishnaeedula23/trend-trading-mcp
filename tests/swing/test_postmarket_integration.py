"""End-to-end: seed active idea → call postmarket endpoint → verify snapshot + event + Slack call."""
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

import pandas as pd

from api.main import app
from tests.fixtures.swing_fixtures import FakeSupabaseClient


@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.endpoints.swing_postmarket._get_supabase")
def test_full_postmarket_loop_writes_snapshot_and_exhaustion(
    mock_sb, mock_bars, mock_slack, monkeypatch,
):
    monkeypatch.setenv("CRON_SECRET", "t")
    sb = FakeSupabaseClient()
    idea_id = str(uuid4())
    sb.table("swing_ideas").insert([{
        "id": idea_id, "ticker": "NVDA", "status": "triggered",
        "cycle_stage": "base_n_break", "stop_price": 50.0,
        "setup_kell": "base_n_break", "direction": "long",
        "risk_flags": {},
    }])
    # Far-above-10ema to trigger exhaustion
    closes = [100.0] * 50 + [200.0]
    n = len(closes)
    mock_bars.return_value = pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=n, freq="B"),
        "open": [c * 0.995 for c in closes],
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1_000_000] * n,
    })
    mock_sb.return_value = sb

    client = TestClient(app)
    r = client.post(
        "/api/swing/pipeline/postmarket",
        headers={"Authorization": "Bearer t"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active_ideas_processed"] == 1
    assert body["exhaustion_warnings"] == 1
    assert body["snapshots_written"] == 1
    assert mock_slack.called

    assert sb.table("swing_ideas").rows[0]["risk_flags"]["far_above_10ema"] is True
    assert any(
        e["event_type"] == "exhaustion_warning"
        for e in sb.table("swing_events").rows
    )
