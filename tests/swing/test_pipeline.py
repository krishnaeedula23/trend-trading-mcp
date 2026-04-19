"""Tests for api.indicators.swing.pipeline.run_premarket_detection."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pandas as pd
import pytest

from api.indicators.swing.setups import synth_bars
from api.indicators.swing.universe.resolver import save_universe_batch
from api.indicators.swing.pipeline import run_premarket_detection
from tests.fixtures.swing_fixtures import FakeSupabaseClient


# ── Bar-builder helpers ────────────────────────────────────────────────────────

def _flat_bars(n: int = 50, close: float = 100.0) -> pd.DataFrame:
    """Return n flat bars — guaranteed to have enough bars but won't trigger detectors."""
    return synth_bars(days=n, start="2025-09-01")


def _wedge_pop_bars() -> pd.DataFrame:
    """Replicate the happy-path fixture from test_setups_wedge_pop so the Wedge Pop
    detector fires reliably.  36 bars total (35 flat + 1 reclaim bar).
    """
    closes = [100.0] * 35 + [103.0]
    df = synth_bars(closes=closes, start="2025-09-01")

    window_highs = [108.0 - i for i in range(15)]         # 108 → 94 (descending)
    window_lows  = [92.0 - i * 0.3 for i in range(15)]    # 92.0 → 87.8
    df.loc[df.index[20:35], "high"] = window_highs
    df.loc[df.index[20:35], "low"]  = window_lows

    # Current bar: low above window min, volume spike
    df.loc[df.index[-1], "low"]    = 102.0 * 0.99
    df.loc[df.index[-1], "volume"] = int(10_000_000 * 1.35)  # 1.35× avg → above 1.2 threshold
    return df


def _make_test_fetcher(bars_map: dict[str, pd.DataFrame]):
    def _fetch(tickers, period="1y"):
        return {t: bars_map[t] for t in tickers if t in bars_map}
    return _fetch


# ── Test 1: End-to-end smoke ───────────────────────────────────────────────────

def test_smoke_pipeline_runs_and_returns_expected_shape(monkeypatch):
    """Pipeline runs without errors on a 2-ticker universe, handles empty hits,
    and returns a dict with all expected keys.
    """
    sb = FakeSupabaseClient()
    save_universe_batch(sb, {"AAPL": {}, "NVDA": {}}, source="deepvue-csv")

    qqq_bars = _flat_bars(50, close=420.0)
    aapl_bars = _flat_bars(50, close=180.0)
    nvda_bars = _flat_bars(50, close=800.0)

    fetcher = _make_test_fetcher({
        "QQQ": qqq_bars,
        "AAPL": aapl_bars,
        "NVDA": nvda_bars,
    })

    mock_post = AsyncMock(return_value=True)
    monkeypatch.setattr("api.indicators.swing.pipeline.post_premarket_digest", mock_post)

    result = run_premarket_detection(sb, fetch_bars=fetcher)

    assert set(result.keys()) == {
        "new_ideas", "transitions", "invalidations",
        "universe_source", "universe_size", "market_health",
    }
    assert result["universe_source"] == "deepvue"
    assert result["universe_size"] == 2
    assert result["invalidations"] == 0
    assert isinstance(result["market_health"], dict)
    assert "qqq_close" in result["market_health"]

    # Slack post must have been called exactly once
    mock_post.assert_awaited_once()


# ── Test 2: Idempotency ────────────────────────────────────────────────────────

def test_idempotency_no_duplicate_ideas(monkeypatch):
    """Pre-seeded idea for AAPL/wedge_pop/today → pipeline must not insert a duplicate."""
    sb = FakeSupabaseClient()
    save_universe_batch(sb, {"AAPL": {}}, source="deepvue-csv")

    today_str = datetime.now(timezone.utc).date().isoformat()

    # Pre-seed an existing idea for AAPL/wedge_pop detected today
    existing_idea = {
        "id": str(uuid4()),
        "ticker": "AAPL",
        "setup_kell": "wedge_pop",
        "cycle_stage": "wedge_pop",
        "confluence_score": 7,
        "entry_zone_low": 103.0,
        "entry_zone_high": 105.06,
        "stop_price": 100.98,
        "first_target": 110.0,
        "second_target": None,
        "status": "active",
        "detected_at": f"{today_str}T06:00:00+00:00",
        "detection_evidence": {},
        "market_health": {},
        "risk_flags": {},
        "base_thesis": None,
        "thesis_status": "pending",
    }
    sb.table("swing_ideas").insert(existing_idea).execute()

    wedge_bars = _wedge_pop_bars()
    qqq_bars = _flat_bars(len(wedge_bars), close=420.0)

    fetcher = _make_test_fetcher({
        "QQQ": qqq_bars,
        "AAPL": wedge_bars,
    })

    mock_post = AsyncMock(return_value=True)
    monkeypatch.setattr("api.indicators.swing.pipeline.post_premarket_digest", mock_post)

    run_premarket_detection(sb, fetch_bars=fetcher)

    # Exactly 1 row for AAPL/wedge_pop — no duplicate
    aapl_ideas = [
        r for r in sb.table("swing_ideas").select("*").execute().data
        if r["ticker"] == "AAPL" and r["setup_kell"] == "wedge_pop"
    ]
    assert len(aapl_ideas) == 1, f"Expected 1 idea, got {len(aapl_ideas)}"


# ── Test 3: Empty universe ─────────────────────────────────────────────────────

def test_empty_universe_returns_zeros_and_no_slack(monkeypatch):
    """Empty universe → zeros returned immediately, Slack never called."""
    sb = FakeSupabaseClient()  # no universe rows seeded

    mock_post = AsyncMock(return_value=True)
    monkeypatch.setattr("api.indicators.swing.pipeline.post_premarket_digest", mock_post)

    # fetcher should never be called — pass one that tracks calls
    call_count = {"n": 0}

    def counting_fetcher(tickers, period="1y"):
        call_count["n"] += 1
        return {}

    result = run_premarket_detection(sb, fetch_bars=counting_fetcher)

    assert result == {
        "new_ideas": 0,
        "transitions": 0,
        "invalidations": 0,
        "universe_source": "empty",
        "universe_size": 0,
        "market_health": {},
    }
    mock_post.assert_not_awaited()
    assert call_count["n"] == 0, "fetch_bars should not be called for empty universe"


# ── Test 4: End-to-end detector fires + row inserted ───────────────────────────

def test_detector_fires_inserts_idea_and_calls_slack(monkeypatch):
    """Integration check: Wedge Pop bars through the pipeline must insert a
    swing_ideas row and include the hit in the Slack digest call.

    Regression guard — catches detector-signature mismatches like the
    post_eps_flag fix in commit after 5b3c9c2: if a detector raises, the pipeline's
    broad per-ticker try/except swallows it and new_ideas stays 0.
    """
    sb = FakeSupabaseClient()
    save_universe_batch(sb, {"AAPL": {}}, source="deepvue-csv")

    wedge_bars = _wedge_pop_bars()
    qqq_bars = _flat_bars(len(wedge_bars), close=420.0)

    fetcher = _make_test_fetcher({"QQQ": qqq_bars, "AAPL": wedge_bars})
    mock_post = AsyncMock(return_value=True)
    monkeypatch.setattr("api.indicators.swing.pipeline.post_premarket_digest", mock_post)

    result = run_premarket_detection(sb, fetch_bars=fetcher)

    assert result["new_ideas"] >= 1, "Wedge Pop should fire and insert at least 1 idea"
    rows = sb.table("swing_ideas").select("*").execute().data
    assert any(r["ticker"] == "AAPL" and r["setup_kell"] == "wedge_pop" for r in rows)
    mock_post.assert_awaited_once()
