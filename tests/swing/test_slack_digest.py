"""Tests for pre-market Slack digest formatter."""

from unittest.mock import AsyncMock

from api.indicators.swing.setups import SetupHit
from api.indicators.swing.market_health import MarketHealth
from api.indicators.swing.slack_digest import format_premarket_digest, post_premarket_digest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hit(
    ticker: str,
    setup_kell: str = "wedge_pop",
    raw_score: int = 3,
    entry_zone: tuple[float, float] = (480.0, 490.0),
    stop_price: float = 470.0,
    first_target: float | None = 510.0,
    second_target: float | None = 545.0,
) -> SetupHit:
    return SetupHit(
        ticker=ticker,
        setup_kell=setup_kell,
        cycle_stage="stage2",
        entry_zone=entry_zone,
        stop_price=stop_price,
        first_target=first_target,
        second_target=second_target,
        detection_evidence={},
        raw_score=raw_score,
    )


def _green_health() -> MarketHealth:
    return MarketHealth(
        qqq_close=420.0,
        qqq_20ema=410.0,
        qqq_10ema=415.0,
        green_light=True,
        index_cycle_stage="bull",
        snapshot={},
    )


def _base_kwargs() -> dict:
    return dict(
        market_health=_green_health(),
        universe_source="deepvue",
        universe_size=152,
        universe_age_days=2,
    )


# ── Test 1: 3 hits, 1 transition, 0 invalidations ──────────────────────────────

def test_format_three_hits_one_transition():
    nvda = _hit("NVDA", raw_score=5)
    aapl = _hit("AAPL", setup_kell="ema_crossback", raw_score=4)
    tsla = _hit("TSLA", raw_score=3)
    hits = [(nvda, 9), (aapl, 8), (tsla, 6)]
    transitions = [{"ticker": "CRWD", "from_stage": "wedge_pop", "to_stage": "ema_crossback"}]

    result = format_premarket_digest(
        hits_with_scores=hits,
        transitions=transitions,
        invalidations=[],
        **_base_kwargs(),
    )

    # Header
    assert "🟢 Swing Pre-market" in result
    assert "deepvue (152, 2d ago)" in result
    assert "QQQ green light" in result

    # Top setups section
    assert "Top setups (3):" in result
    # Ranked by score: NVDA(9) first, AAPL(8) second, TSLA(6) third
    lines = result.splitlines()
    nvda_idx = next(i for i, l in enumerate(lines) if "NVDA" in l)
    aapl_idx = next(i for i, l in enumerate(lines) if "AAPL" in l)
    tsla_idx = next(i for i, l in enumerate(lines) if "TSLA" in l)
    assert nvda_idx < aapl_idx < tsla_idx

    # Stage transitions present
    assert "Stage transitions today (1):" in result
    assert "CRWD: wedge_pop → ema_crossback" in result

    # No invalidations section
    assert "Invalidations" not in result

    # Footer always present
    assert "⏳ Analysis pending" in result


# ── Test 2: empty digest ────────────────────────────────────────────────────────

def test_empty_digest_returns_placeholder():
    result = format_premarket_digest(
        hits_with_scores=[],
        transitions=[],
        invalidations=[],
        **_base_kwargs(),
    )
    assert result == "🔴 Swing Pre-market — no setups today"


# ── Test 3: missing second_target uses singular "target" ──────────────────────

def test_missing_second_target_uses_singular():
    hit = _hit("AAPL", first_target=195.0, second_target=None, entry_zone=(187.0, 189.0), stop_price=184.0)
    result = format_premarket_digest(
        hits_with_scores=[(hit, 7)],
        transitions=[],
        invalidations=[],
        **_base_kwargs(),
    )
    # Should contain "target 195" (singular), not "targets"
    assert "target 195" in result
    assert "targets" not in result


# ── Test 4: post_premarket_digest calls send_message ──────────────────────────

async def test_post_premarket_digest_calls_slack(monkeypatch):
    mock_send = AsyncMock(return_value=True)
    monkeypatch.setattr("api.indicators.swing.slack_digest.send_message", mock_send)

    nvda = _hit("NVDA", raw_score=5)
    aapl = _hit("AAPL", raw_score=4)

    result = await post_premarket_digest(
        hits_with_scores=[(nvda, 9), (aapl, 7)],
        transitions=[],
        invalidations=[],
        **_base_kwargs(),
    )

    assert result is True
    mock_send.assert_awaited_once()
    call_args = mock_send.await_args
    # First positional arg is the text
    text_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
    assert "Swing Pre-market" in text_arg
    # channel_type kwarg
    assert call_args.kwargs.get("channel_type") == "swing-trades"
