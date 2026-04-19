from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from api.indicators.swing.pipeline import postmarket as pm
from tests.fixtures.swing_fixtures import FakeSupabaseClient


def _idea(id_="aaaa-1", ticker="NVDA", status="triggered", stop_price=100.0, stage="base_n_break"):
    return {
        "id": id_, "ticker": ticker, "status": status, "cycle_stage": stage,
        "stop_price": stop_price, "entry_zone_low": 110.0, "entry_zone_high": 112.0,
        "first_target": 130.0, "second_target": 150.0,
        "setup_kell": "base_n_break", "direction": "long",
        "risk_flags": {},
    }


def _bars(closes, volumes=None):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=n, freq="B"),
        "open": [c * 0.995 for c in closes],
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": volumes or [1_000_000] * n,
    })


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_writes_snapshot_and_no_exhaustion(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea()])
    mock_bars.return_value = _bars([100.0 + i * 0.1 for i in range(60)])

    result = pm.run_swing_postmarket_snapshot(sb)

    assert result.active_ideas_processed == 1
    assert result.stop_violations == 0
    assert result.exhaustion_warnings == 0
    assert result.snapshots_written == 1
    snaps = sb.table("swing_idea_snapshots").rows
    assert len(snaps) == 1
    assert snaps[0]["idea_id"] == "aaaa-1"


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_detects_stop_violation(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea(stop_price=150.0)])  # stop well above price
    mock_bars.return_value = _bars([100.0] * 60)               # close = 100, stop = 150

    result = pm.run_swing_postmarket_snapshot(sb)

    assert result.stop_violations == 1
    ideas = sb.table("swing_ideas").rows
    assert ideas[0]["status"] == "invalidated"
    assert ideas[0]["invalidated_reason"].startswith("stop")
    events = sb.table("swing_events").rows
    assert any(e["event_type"] == "invalidation" for e in events)


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_writes_exhaustion_warning(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea()])
    # Construct bars that trigger far_above_10ema
    mock_bars.return_value = _bars([100.0] * 50 + [200.0])

    result = pm.run_swing_postmarket_snapshot(sb)

    assert result.exhaustion_warnings == 1
    ideas = sb.table("swing_ideas").rows
    assert ideas[0]["risk_flags"].get("far_above_10ema") is True
    events = sb.table("swing_events").rows
    assert any(e["event_type"] == "exhaustion_warning" for e in events)


@patch("api.indicators.swing.pipeline.postmarket._fetch_daily_bars")
@patch("api.indicators.swing.pipeline.postmarket._post_slack_digest")
def test_postmarket_is_idempotent(mock_slack, mock_bars):
    sb = FakeSupabaseClient()
    sb.table("swing_ideas").insert([_idea()])
    mock_bars.return_value = _bars([100.0 + i * 0.1 for i in range(60)])

    pm.run_swing_postmarket_snapshot(sb)
    pm.run_swing_postmarket_snapshot(sb)   # second run same day

    snaps = sb.table("swing_idea_snapshots").rows
    assert len(snaps) == 1                 # unique (idea_id, snapshot_date, snapshot_type)
