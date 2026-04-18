"""Tests for confluence scoring."""

from api.indicators.swing.confluence import score_hits
from api.indicators.swing.setups import SetupHit
from api.indicators.swing.market_health import MarketHealth


def _hit(raw_score: int, volume_vs_20d_avg: float = 0.5) -> SetupHit:
    return SetupHit(
        ticker="AAPL",
        setup_kell="wedge_pop",
        cycle_stage="stage2",
        entry_zone=(100.0, 102.0),
        stop_price=98.0,
        first_target=110.0,
        second_target=120.0,
        detection_evidence={"volume_vs_20d_avg": volume_vs_20d_avg},
        raw_score=raw_score,
    )


def _red_health() -> MarketHealth:
    return MarketHealth(
        qqq_close=100.0,
        qqq_20ema=110.0,
        qqq_10ema=105.0,
        green_light=False,
        index_cycle_stage="bear",
        snapshot={},
    )


def _green_health() -> MarketHealth:
    return MarketHealth(
        qqq_close=120.0,
        qqq_20ema=110.0,
        qqq_10ema=105.0,
        green_light=True,
        index_cycle_stage="bull",
        snapshot={},
    )


# ── Test 1: Single hit, no bonuses → score == raw_score ────────────────────────

def test_single_hit_baseline():
    hit = _hit(raw_score=3)
    results = score_hits([hit], ticker="AAPL", ctx={}, market_health=_red_health())
    assert len(results) == 1
    assert results[0] == (hit, 3)


# ── Test 2: Two detectors fire → each gets +2 multi_setup_bonus ────────────────

def test_two_hits_multi_setup_bonus():
    h1 = _hit(raw_score=2)
    h2 = _hit(raw_score=3)
    results = score_hits([h1, h2], ticker="AAPL", ctx={}, market_health=_red_health())
    assert results[0] == (h1, 4)   # 2 + 2
    assert results[1] == (h2, 5)   # 3 + 2


# ── Test 3: rs_10d > 0.05 → +1 RS bonus ────────────────────────────────────────

def test_rs_bonus():
    hit = _hit(raw_score=2)
    results = score_hits([hit], ticker="AAPL", ctx={"rs_10d": 0.07}, market_health=_red_health())
    assert results[0][1] == 3   # 2 + 1


# ── Test 4: green_light=True → +1 market bonus ─────────────────────────────────

def test_market_bonus():
    hit = _hit(raw_score=2)
    results = score_hits([hit], ticker="AAPL", ctx={}, market_health=_green_health())
    assert results[0][1] == 3   # 2 + 1


# ── Test 5: all bonuses → clipped at 10 ────────────────────────────────────────

def test_clipped_at_10():
    # 5 + 2 (multi) + 1 (rs) + 1 (market) + 1 (volume) + 1 (theme) = 11 → clipped to 10
    h1 = _hit(raw_score=5, volume_vs_20d_avg=1.6)
    h2 = _hit(raw_score=5, volume_vs_20d_avg=1.6)
    ctx = {"rs_10d": 0.10, "theme_leaders": ["AAPL"]}
    results = score_hits([h1, h2], ticker="AAPL", ctx=ctx, market_health=_green_health())
    assert results[0][1] == 10
    assert results[1][1] == 10


# ── Test 6 (optional): volume_vs_20d_avg > 1.5 → +1 volume bonus ───────────────

def test_volume_bonus():
    hit = _hit(raw_score=2, volume_vs_20d_avg=1.6)
    results = score_hits([hit], ticker="AAPL", ctx={}, market_health=_red_health())
    assert results[0][1] == 3   # 2 + 1


# ── Test 7 (optional): ticker in theme_leaders → +1 theme bonus ────────────────

def test_theme_bonus():
    hit = _hit(raw_score=2)
    ctx = {"theme_leaders": ["AAPL", "NVDA"]}
    results = score_hits([hit], ticker="AAPL", ctx=ctx, market_health=_red_health())
    assert results[0][1] == 3   # 2 + 1


# ── Test 8 (optional): low raw_score guard — score is clipped at 1 ─────────────

def test_clipped_at_1():
    # raw_score=1 with no bonuses → stays at 1 (floor guard)
    hit = _hit(raw_score=1)
    results = score_hits([hit], ticker="AAPL", ctx={}, market_health=_red_health())
    assert results[0][1] == 1
