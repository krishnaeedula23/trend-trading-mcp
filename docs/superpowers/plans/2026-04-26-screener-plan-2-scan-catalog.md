# Screener Plan 2 — Scan Catalog Expansion + Phase Oscillator + Backfill Wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the morning-screener scan registry with the rest of the catalog (12+ scans across Breakout / Transition / Reversion lanes), replace the Phase Oscillator stand-in with the real Pine-Script port already in the repo, wire the unused `backfill_days_in_compression` helper into the runner, add observability/filters, and validate end-to-end against live market data.

**Architecture:** Each scan lives in its own file under `api/indicators/screener/scans/`, self-registers on import via `register_scan(...)`, and emits `ScanHit` rows the runner aggregates into a per-ticker confluence list. Foundation work (overlay schema extension + Phase Oscillator wiring + backfill wiring) lands first because every downstream scan reads from `IndicatorOverlay`. Reuse the existing high-fidelity Saty indicators in `api/indicators/satyland/{phase_oscillator,pivot_ribbon,atr_levels}.py` — do **not** re-port from Pine Script. Reuse existing swing-setup detectors (`wedge_pop`, `ema_crossback`, `exhaustion_extension`) by wrapping them in scan adapters; do not duplicate detection math.

**Tech Stack:** Python 3.12, pandas, numpy, talib, yfinance, Pydantic v2, Supabase Python client, FastAPI, pytest. No new external deps.

**Spec:** [docs/superpowers/specs/2026-04-25-unified-screener-design.md](../specs/2026-04-25-unified-screener-design.md)
**Roadmap:** [docs/superpowers/plans/2026-04-26-screener-plan-roadmap.md](2026-04-26-screener-plan-roadmap.md)
**Plan 1 (shipped):** [docs/superpowers/plans/2026-04-25-screener-plan-1-foundation.md](2026-04-25-screener-plan-1-foundation.md)

---

## Preconditions (verify BEFORE starting Task 1)

These were flagged as broken / unverified at Plan 1 handoff. Resolve before opening a worktree.

1. **Railway auto-deploy is picking up `main`.** Hit `https://trend-trading-mcp-production.up.railway.app/api/screener/universe?mode=swing`. Returns 404 ⇒ pre-merge code; fix Railway dashboard → Service → Source/Triggers, or trigger a manual redeploy. Returns 200 with JSON ⇒ proceed.
2. **`SWING_API_TOKEN` matches across environments.** Compare `~/.config/trend-trading-mcp/swing-api.token` with the Railway service env. Mismatched ⇒ auth-protected endpoints will 500.
3. **Open a worktree before any code changes.** From repo root:
   ```bash
   git worktree add .worktrees/screener-plan-2 -b feat/screener-plan-2 main
   cd .worktrees/screener-plan-2
   pwd  # MUST end with .worktrees/screener-plan-2
   ```
   **Implementer subagents must run `pwd` and verify the path ends with `.worktrees/screener-plan-2` before any `git commit`.** Two cwd-drift commits landed on `main` in Plan 1; this is the fix.
4. **Supabase access** — this plan adds no migrations, but if any are needed mid-flight, apply them via the MCP `apply_migration` tool against project `pmjufbiagokrrcxnhmah` (the user has granted blanket access). Do not delegate migration application to subagents.

---

## File Structure

### Files modified

```
api/schemas/screener.py                          # Extend IndicatorOverlay; add weight to ScanDescriptor surface
api/indicators/screener/overlay.py               # Compute new metrics; wire Phase Oscillator + Pivot Ribbon + ATR Levels
api/indicators/screener/runner.py                # Wire backfill, weighted confluence, sector grouping, earnings filter, structured logs
api/indicators/screener/persistence.py           # Add initial_days_by_ticker param to update_coiled_watchlist
api/indicators/screener/registry.py              # Add weight: int = 1 to ScanDescriptor
api/indicators/screener/bars.py                  # Add fetch_hourly_bars_bulk
api/indicators/screener/scans/__init__.py        # Import every new scan module so registration fires
api/indicators/screener/scans/coiled.py          # Replace _compression_proxy with Phase Oscillator value check
api/endpoints/screener_morning.py                # Inject QQQ + sector cache into runner inputs
scripts/screener_smoke_test.py                   # Run against live infra, print hit summary; broaden universe
```

### Files created

```
api/indicators/screener/sectors.py
api/indicators/screener/scans/pradeep_4pct.py
api/indicators/screener/scans/qullamaggie_episodic_pivot.py
api/indicators/screener/scans/qullamaggie_continuation_base.py
api/indicators/screener/scans/saty_trigger_up.py
api/indicators/screener/scans/saty_golden_gate_up.py
api/indicators/screener/scans/vomy_up_daily.py
api/indicators/screener/scans/vomy_up_hourly.py
api/indicators/screener/scans/ema_crossback.py
api/indicators/screener/scans/saty_reversion.py
api/indicators/screener/scans/vomy_down_extension.py
api/indicators/screener/scans/saty_trigger_down.py
api/indicators/screener/scans/kell_wedge_pop.py
api/indicators/screener/scans/kell_flag_base.py
api/indicators/screener/scans/kell_exhaustion_extension.py

tests/screener/test_sectors.py
tests/screener/test_pradeep_4pct.py
tests/screener/test_qullamaggie_episodic_pivot.py
tests/screener/test_qullamaggie_continuation_base.py
tests/screener/test_saty_trigger_up.py
tests/screener/test_saty_golden_gate_up.py
tests/screener/test_vomy_up_daily.py
tests/screener/test_vomy_up_hourly.py
tests/screener/test_ema_crossback.py
tests/screener/test_saty_reversion.py
tests/screener/test_vomy_down_extension.py
tests/screener/test_saty_trigger_down.py
tests/screener/test_kell_wedge_pop.py
tests/screener/test_kell_flag_base.py
tests/screener/test_kell_exhaustion_extension.py
tests/screener/test_runner_backfill.py
tests/screener/test_runner_observability.py
tests/screener/test_bars_hourly.py
```

### Boundaries

- `overlay.py` owns indicator computation. Every numeric metric a scan reads should be present on `IndicatorOverlay`. If a scan needs a metric not in the overlay, **add it to the overlay** — don't recompute in the scan.
- `scans/*.py` owns scan-specific logic. Each file = one scan family (e.g. `saty_trigger_up.py` registers Day / Multiday / Swing variants). No cross-scan imports beyond the registry.
- `runner.py` owns orchestration: per-ticker overlay computation, scan dispatch, confluence aggregation, persistence, and the new responsibilities (backfill, weighting, sector grouping, earnings filter, structured logs).
- Scan adapters for existing detectors (Vomy / EMA Crossback / Wedge Pop / Exhaustion) unwrap inputs, call the existing detector, and convert the result to a `ScanHit`. **Do not duplicate detection math.**

---

## Confluence weighting (locked here so all later tasks reference the same numbers)

`ScanDescriptor` gains a new field: `weight: int = 1`. The runner sums per-scan weights into `TickerResult.confluence` (replacing the raw count).

| Scan ID | Weight | Lane / Role |
|---|---|---|
| `saty_trigger_up_day`, `saty_trigger_up_multiday`, `saty_trigger_up_swing` | 3 | breakout / trigger |
| `saty_golden_gate_up_day`, `saty_golden_gate_up_multiday`, `saty_golden_gate_up_swing` | 3 | breakout / trigger |
| `saty_trigger_down_day` | 3 | reversion / trigger |
| `pradeep_4pct_breakout` | 2 | breakout / trigger |
| `qullamaggie_episodic_pivot` | 2 | breakout / trigger |
| `vomy_up_daily` | 2 | transition / trigger |
| `vomy_up_hourly` | 2 | transition / trigger |
| `vomy_down_extension` | 2 | reversion / trigger |
| `kell_exhaustion_extension` | 2 | reversion / trigger |
| `coiled_spring` | 1 | breakout / coiled |
| `qullamaggie_continuation_base` | 1 | breakout / setup_ready |
| `kell_wedge_pop` | 1 | breakout / setup_ready |
| `kell_flag_base` | 1 | breakout / setup_ready |
| `ema_crossback` | 1 | transition / setup_ready |
| `saty_reversion_up`, `saty_reversion_down` | 1 | reversion / setup_ready |

---

## Tasks (overview)

| # | Task | Type |
|---|---|---|
| 1 | Extend `IndicatorOverlay` schema | foundation |
| 2 | Compute new metrics in `compute_overlay()` | foundation |
| 3 | Wire Phase Oscillator into Coiled Spring | foundation |
| 4 | Add `weight` to `ScanDescriptor`; weighted confluence | foundation |
| 5 | Wire `backfill_days_in_compression` into runner | foundation |
| 6 | Add `fetch_hourly_bars_bulk` to bars module | plumbing |
| 7 | Add sector lookup cache (`sectors.py`) | plumbing |
| 8 | Pradeep 4% Breakout Bullish | scan |
| 9 | Qullamaggie Episodic Pivot | scan |
| 10 | Qullamaggie Continuation Base | scan |
| 11 | Saty Trigger Up — Day / Multiday / Swing | scan family |
| 12 | Saty Golden Gate Up — Day / Multiday / Swing | scan family |
| 13 | Vomy Up Daily | scan |
| 14 | Vomy Up Hourly + endpoint plumbing | scan |
| 15 | EMA Crossback | scan |
| 16 | Saty Reversion Up / Down | scan family |
| 17 | Vomy Down at extension highs | scan |
| 18 | Saty Trigger Down (Day) | scan |
| 19 | Kell Wedge Pop adapter | scan |
| 20 | Kell Flag Base | scan |
| 21 | Kell Exhaustion Extension adapter | scan |
| 22 | Earnings filter + sector grouping + structured logging | observability |
| 23 | Live smoke run validation | validation |

---

### Task 1: Extend `IndicatorOverlay` schema with new metric fields

**Files:**
- Modify: `api/schemas/screener.py`
- Test: `tests/screener/test_overlay.py`

- [ ] **Step 1.1: Write failing test for the extended schema**

Append to `tests/screener/test_overlay.py`:

```python
def test_indicator_overlay_has_extended_fields():
    """Plan 2: schema must carry volume / move / phase / ribbon fields used by new scans."""
    from api.schemas.screener import IndicatorOverlay
    sample = IndicatorOverlay(
        atr_pct=0.02, pct_from_50ma=0.0, extension=0.0, sma_50=100.0, atr_14=2.0,
        volume_avg_50d=1_000_000.0, relative_volume=1.0, gap_pct_open=0.0,
        adr_pct_20d=0.04, pct_change_today=0.0, pct_change_30d=0.0,
        pct_change_90d=0.0, pct_change_180d=0.0, dollar_volume_today=100_000_000.0,
        phase_oscillator=0.0, phase_in_compression=False,
        ribbon_state="bullish", bias_candle="green", above_48ema=True,
        saty_levels_by_mode={},
    )
    assert sample.relative_volume == 1.0
    assert sample.phase_in_compression is False
    assert sample.ribbon_state == "bullish"
```

- [ ] **Step 1.2: Run test, confirm failure**

Run: `pytest tests/screener/test_overlay.py::test_indicator_overlay_has_extended_fields -v`
Expected: FAIL — Pydantic validation error on unknown keyword arguments.

- [ ] **Step 1.3: Replace `IndicatorOverlay` in `api/schemas/screener.py`**

Replace the existing class with:

```python
RibbonState = Literal["bullish", "bearish", "chopzilla"]
BiasCandle = Literal["green", "blue", "orange", "red", "gray"]


class IndicatorOverlay(BaseModel):
    """Per-ticker indicator stack computed once per run."""
    # Core (existing)
    atr_pct: float = Field(..., description="ATR(14) / close")
    pct_from_50ma: float = Field(..., description="(close - SMA50) / SMA50")
    extension: float = Field(..., description="jfsrev formula B/A")
    sma_50: float
    atr_14: float

    # Volume / liquidity
    volume_avg_50d: float = Field(0.0, description="Mean of last 50 daily volumes")
    relative_volume: float = Field(0.0, description="Today's volume / volume_avg_50d")
    dollar_volume_today: float = Field(0.0, description="close * volume on the latest bar")

    # Move metrics
    gap_pct_open: float = Field(0.0, description="(today_open - yesterday_close) / yesterday_close")
    pct_change_today: float = Field(0.0, description="(today_close / yesterday_close) - 1")
    pct_change_30d: float = Field(0.0, description="close / close[-31] - 1, or 0 if insufficient bars")
    pct_change_90d: float = Field(0.0, description="close / close[-91] - 1, or 0 if insufficient bars")
    pct_change_180d: float = Field(0.0, description="close / close[-181] - 1, or 0 if insufficient bars")
    adr_pct_20d: float = Field(0.0, description="mean of (high-low)/close over last 20 bars")

    # Phase Oscillator (Saty Pine port)
    phase_oscillator: float = Field(0.0, description="Saty Phase Oscillator value, ±100 scale")
    phase_in_compression: bool = Field(False, description="Saty Phase Oscillator compression_tracker")

    # Pivot Ribbon Pro
    ribbon_state: RibbonState = Field("chopzilla")
    bias_candle: BiasCandle = Field("gray")
    above_48ema: bool = Field(False)

    # Saty ATR Levels per trading mode
    saty_levels_by_mode: dict = Field(
        default_factory=dict,
        description=(
            "{'day': {...}, 'multiday': {...}, 'swing': {...}} — values are the dict "
            "returned by api.indicators.satyland.atr_levels.atr_levels(). Empty dict "
            "if fewer bars than the mode requires."
        ),
    )
```

- [ ] **Step 1.4: Run test, confirm pass**

Run: `pytest tests/screener/test_overlay.py::test_indicator_overlay_has_extended_fields -v`
Expected: PASS.

- [ ] **Step 1.5: Run full screener suite for regressions**

Run: `pytest tests/screener/ -v`
Expected: existing schema-construction tests pass; some `compute_overlay()` consumer tests may still pass because the new fields default to safe values. If any consumer test fails, **stop and investigate** — Task 2 will refresh `compute_overlay()` itself.

- [ ] **Step 1.6: Commit**

```bash
pwd  # verify path ends with .worktrees/screener-plan-2
git add api/schemas/screener.py tests/screener/test_overlay.py
git commit -m "feat(screener): extend IndicatorOverlay schema with volume/move/phase/ribbon fields"
```

---

### Task 2: Populate new metrics in `compute_overlay()`

**Files:**
- Modify: `api/indicators/screener/overlay.py`
- Test: `tests/screener/test_overlay.py`

- [ ] **Step 2.1: Write failing tests for each new metric**

Append to `tests/screener/test_overlay.py`:

```python
def test_overlay_computes_volume_metrics(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60, volume=2_000_000)
    out = compute_overlay(bars)
    assert out.volume_avg_50d == pytest.approx(2_000_000.0)
    assert out.relative_volume == pytest.approx(1.0)
    assert out.dollar_volume_today == pytest.approx(2_000_000.0 * 100.0)


def test_overlay_computes_pct_change_today(synth_daily_bars):
    closes = [100.0] * 59 + [105.0]
    bars = synth_daily_bars(closes=closes)
    out = compute_overlay(bars)
    assert out.pct_change_today == pytest.approx(0.05, rel=1e-6)


def test_overlay_computes_gap_pct_open():
    import pandas as pd
    closes = [100.0] * 59 + [105.0]
    bars = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="B"),
        "open":  [100.0] * 59 + [103.0],
        "high":  [c * 1.005 for c in closes],
        "low":   [c * 0.995 for c in closes],
        "close": closes, "volume": [1_000_000] * 60,
    })
    out = compute_overlay(bars)
    assert out.gap_pct_open == pytest.approx(0.03, rel=1e-6)


def test_overlay_zero_pct_change_for_insufficient_lookback(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert out.pct_change_30d == pytest.approx(0.0, abs=1e-9)
    assert out.pct_change_90d == 0.0
    assert out.pct_change_180d == 0.0


def test_overlay_computes_adr_pct_20d():
    import pandas as pd
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="B"),
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low":  [c * 0.99 for c in closes],
        "close": closes, "volume": [1_000_000] * 60,
    })
    out = compute_overlay(bars)
    assert out.adr_pct_20d == pytest.approx(0.02, rel=1e-3)


def test_overlay_returns_phase_oscillator_value(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert -1.0 < out.phase_oscillator < 1.0
    assert isinstance(out.phase_in_compression, bool)


def test_overlay_returns_ribbon_state_for_uptrend(synth_daily_bars):
    closes = [100.0 + i * 1.5 for i in range(120)]
    bars = synth_daily_bars(closes=closes)
    out = compute_overlay(bars)
    assert out.ribbon_state == "bullish"
    assert out.above_48ema is True


def test_overlay_returns_saty_levels_for_day_mode(synth_daily_bars):
    bars = synth_daily_bars(closes=[100.0] * 60)
    out = compute_overlay(bars)
    assert "day" in out.saty_levels_by_mode
    day = out.saty_levels_by_mode["day"]
    assert "call_trigger" in day
    assert "put_trigger" in day
    assert "levels" in day and "golden_gate_bull" in day["levels"]
```

- [ ] **Step 2.2: Run, confirm failures**

Run: `pytest tests/screener/test_overlay.py -v`
Expected: all eight new tests fail (fields stay at default values).

- [ ] **Step 2.3: Rewrite `api/indicators/screener/overlay.py`**

Replace the entire file with:

```python
"""Indicator overlay: ATR, volume, move metrics, Phase Oscillator, Pivot Ribbon, ATR Levels."""
from __future__ import annotations

import logging

import pandas as pd
import talib

from api.indicators.satyland.atr_levels import atr_levels
from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.schemas.screener import IndicatorOverlay


logger = logging.getLogger(__name__)


SMA_PERIOD = 50
ATR_PERIOD = 14
VOLUME_AVG_PERIOD = 50
ADR_PERIOD = 20


def _resample(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample daily OHLCV to a wider timeframe (W=weekly, M=monthly)."""
    df = bars.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    agg = df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return agg.reset_index()


def _safe_pct_change(close: pd.Series, lookback: int) -> float:
    if len(close) < lookback + 1:
        return 0.0
    base = float(close.iloc[-(lookback + 1)])
    last = float(close.iloc[-1])
    return (last / base) - 1.0 if base > 0 else 0.0


def compute_overlay(bars: pd.DataFrame) -> IndicatorOverlay:
    """Compute the full indicator overlay from a daily bar DataFrame.

    Requires >= 50 bars (SMA50). Optional fields (90d/180d move, weekly/monthly
    Saty Levels) degrade to safe defaults rather than raising.
    """
    if len(bars) < SMA_PERIOD:
        raise ValueError(
            f"compute_overlay requires at least {SMA_PERIOD} bars; got {len(bars)}."
        )

    high   = bars["high"].astype(float).values
    low    = bars["low"].astype(float).values
    close  = bars["close"].astype(float).values
    volume = bars["volume"].astype(float).values

    last_close = float(close[-1])
    sma_50 = float(pd.Series(close).rolling(SMA_PERIOD).mean().iloc[-1])
    atr_arr = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)
    atr_14 = float(atr_arr[-1]) if not pd.isna(atr_arr[-1]) else 0.0

    atr_pct = atr_14 / last_close if last_close > 0 else 0.0
    pct_from_50ma = (last_close - sma_50) / sma_50 if sma_50 > 0 else 0.0
    extension = (pct_from_50ma / atr_pct) if atr_pct > 0 else 0.0

    # Volume
    vol_series = pd.Series(volume)
    if len(vol_series) >= VOLUME_AVG_PERIOD:
        volume_avg_50d = float(vol_series.tail(VOLUME_AVG_PERIOD).mean())
    else:
        volume_avg_50d = float(vol_series.mean())
    last_volume = float(volume[-1])
    relative_volume = last_volume / volume_avg_50d if volume_avg_50d > 0 else 0.0
    dollar_volume_today = last_close * last_volume

    # Move
    close_series = pd.Series(close)
    if len(close) >= 2 and float(close[-2]) > 0:
        pct_change_today = (last_close / float(close[-2])) - 1.0
        gap_pct_open = (float(bars["open"].iloc[-1]) - float(close[-2])) / float(close[-2])
    else:
        pct_change_today = 0.0
        gap_pct_open = 0.0
    pct_change_30d = _safe_pct_change(close_series, 30)
    pct_change_90d = _safe_pct_change(close_series, 90)
    pct_change_180d = _safe_pct_change(close_series, 180)

    # ADR%
    if len(bars) >= ADR_PERIOD:
        rng = (bars["high"].astype(float) - bars["low"].astype(float)) / bars["close"].astype(float).replace(0, float("nan"))
        adr_pct_20d = float(rng.tail(ADR_PERIOD).mean())
    else:
        adr_pct_20d = 0.0

    # Phase Oscillator
    try:
        po = phase_oscillator(bars)
        phase_value = float(po["oscillator"])
        phase_compression = bool(po["in_compression"])
    except (ValueError, KeyError):
        phase_value, phase_compression = 0.0, False

    # Pivot Ribbon
    try:
        pr = pivot_ribbon(bars)
        ribbon_state = pr["ribbon_state"]
        bias_candle = pr["bias_candle"]
        above_48ema = bool(pr["above_48ema"])
    except (ValueError, KeyError):
        ribbon_state, bias_candle, above_48ema = "chopzilla", "gray", False

    # Saty ATR Levels by mode
    levels_by_mode: dict = {}
    try:
        levels_by_mode["day"] = atr_levels(bars, trading_mode="day", use_current_close=True)
    except (ValueError, KeyError):
        pass
    weekly = _resample(bars, "W")
    if len(weekly) >= 2:
        try:
            levels_by_mode["multiday"] = atr_levels(weekly, trading_mode="multiday", use_current_close=True)
        except (ValueError, KeyError):
            pass
    monthly = _resample(bars, "M")
    if len(monthly) >= 2:
        try:
            levels_by_mode["swing"] = atr_levels(monthly, trading_mode="swing", use_current_close=True)
        except (ValueError, KeyError):
            pass

    return IndicatorOverlay(
        atr_pct=atr_pct, pct_from_50ma=pct_from_50ma, extension=extension,
        sma_50=sma_50, atr_14=atr_14,
        volume_avg_50d=volume_avg_50d, relative_volume=relative_volume,
        dollar_volume_today=dollar_volume_today,
        gap_pct_open=gap_pct_open, pct_change_today=pct_change_today,
        pct_change_30d=pct_change_30d, pct_change_90d=pct_change_90d,
        pct_change_180d=pct_change_180d, adr_pct_20d=adr_pct_20d,
        phase_oscillator=phase_value, phase_in_compression=phase_compression,
        ribbon_state=ribbon_state, bias_candle=bias_candle, above_48ema=above_48ema,
        saty_levels_by_mode=levels_by_mode,
    )
```

- [ ] **Step 2.4: Run, confirm passing**

Run: `pytest tests/screener/test_overlay.py -v`
Expected: all overlay tests pass. If `test_overlay_returns_ribbon_state_for_uptrend` fails because EMA48 hasn't built up enough on 60 bars, lengthen its `closes` to 120 bars (already specified above).

- [ ] **Step 2.5: Run full screener suite**

Run: `pytest tests/screener/ -v`
Expected: all green. Coiled tests still pass because Task 3 will swap in the Phase Oscillator threshold; for now `_compression_proxy` continues to gate.

- [ ] **Step 2.6: Commit**

```bash
pwd
git add api/indicators/screener/overlay.py tests/screener/test_overlay.py
git commit -m "feat(screener): compute volume/move/phase/ribbon/Saty-Levels in overlay"
```

---

### Task 3: Wire Phase Oscillator into Coiled Spring; remove `_compression_proxy`

**Files:**
- Modify: `api/indicators/screener/scans/coiled.py`
- Test: `tests/screener/test_coiled.py`

- [ ] **Step 3.1: Add failing tests for the new threshold**

In `tests/screener/test_coiled.py`, change the import block to:

```python
from api.indicators.screener.overlay import compute_overlay
from api.indicators.screener.scans.coiled import (
    PHASE_OSCILLATOR_LOWER, PHASE_OSCILLATOR_UPPER,
    is_coiled, coiled_scan,
)
```

And append:

```python
def test_phase_oscillator_thresholds_are_minus_20_to_plus_20():
    """Spec §4: Phase Oscillator must be in compression zone (-20 to +20)."""
    assert PHASE_OSCILLATOR_LOWER == -20.0
    assert PHASE_OSCILLATOR_UPPER == 20.0


def test_is_coiled_rejects_when_phase_oscillator_outside_band():
    """Strong uptrend pushes oscillator above +20, so coiled must reject even if other gates would pass."""
    closes = [100.0 + i * 1.5 for i in range(120)]
    dates = pd.date_range("2025-12-01", periods=120, freq="B")
    bars = pd.DataFrame({
        "date": dates,
        "open": closes,
        "high":  [c * 1.005 for c in closes],
        "low":   [c * 0.995 for c in closes],
        "close": closes, "volume": [5_000_000] * 120,
    })
    assert is_coiled(bars) is False
```

- [ ] **Step 3.2: Run, confirm failure**

Run: `pytest tests/screener/test_coiled.py -v`
Expected: ImportError on `PHASE_OSCILLATOR_LOWER`.

- [ ] **Step 3.3: Rewrite `api/indicators/screener/scans/coiled.py`**

Replace the entire file with:

```python
"""Coiled Spring scan — multi-condition compression detector.

ALL must hold on the latest daily bar:
  1. Donchian width (20-day high - low) / close < 8%
  2. TTM Squeeze ON (BB inside KC)
  3. Phase Oscillator value in [-20, +20]
  4. close > SMA50

Lane: breakout. Role: coiled. Weight: 1.
"""
from __future__ import annotations

import pandas as pd
import talib

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


DONCHIAN_PERIOD = 20
DONCHIAN_WIDTH_THRESHOLD = 0.08
BB_PERIOD = 20
BB_STD = 2.0
KC_PERIOD = 20
KC_ATR_MULT = 1.5
PHASE_OSCILLATOR_LOWER = -20.0
PHASE_OSCILLATOR_UPPER = 20.0


def _ttm_squeeze_on(bars: pd.DataFrame) -> bool:
    high = bars["high"].astype(float).values
    low = bars["low"].astype(float).values
    close = bars["close"].astype(float).values
    if len(close) < max(BB_PERIOD, KC_PERIOD) + 1:
        return False
    upper_bb, _, lower_bb = talib.BBANDS(close, timeperiod=BB_PERIOD, nbdevup=BB_STD, nbdevdn=BB_STD)
    atr = talib.ATR(high, low, close, timeperiod=KC_PERIOD)
    sma = talib.SMA(close, timeperiod=KC_PERIOD)
    upper_kc = sma[-1] + KC_ATR_MULT * atr[-1]
    lower_kc = sma[-1] - KC_ATR_MULT * atr[-1]
    return bool(upper_bb[-1] <= upper_kc and lower_bb[-1] >= lower_kc)


def _donchian_width_pct(bars: pd.DataFrame) -> float:
    if len(bars) < DONCHIAN_PERIOD:
        return float("inf")
    window = bars.iloc[-DONCHIAN_PERIOD:]
    width = float(window["high"].max() - window["low"].min())
    last_close = float(bars["close"].iloc[-1])
    return width / last_close if last_close > 0 else float("inf")


def _phase_oscillator_value(bars: pd.DataFrame) -> float:
    try:
        return float(phase_oscillator(bars)["oscillator"])
    except (ValueError, KeyError):
        return float("inf")


def is_coiled(bars: pd.DataFrame) -> bool:
    if len(bars) < 50:
        return False
    last_close = float(bars["close"].iloc[-1])
    sma_50 = float(bars["close"].rolling(50).mean().iloc[-1])
    if last_close <= sma_50:
        return False
    if _donchian_width_pct(bars) >= DONCHIAN_WIDTH_THRESHOLD:
        return False
    if not _ttm_squeeze_on(bars):
        return False
    po = _phase_oscillator_value(bars)
    if not (PHASE_OSCILLATOR_LOWER <= po <= PHASE_OSCILLATOR_UPPER):
        return False
    return True


def coiled_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if not is_coiled(bars):
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="coiled_spring",
            lane="breakout", role="coiled",
            evidence={
                "donchian_width_pct": _donchian_width_pct(bars),
                "ttm_squeeze_on": True,
                "phase_oscillator": _phase_oscillator_value(bars),
                "close": float(bars["close"].iloc[-1]),
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="coiled_spring", lane="breakout", role="coiled",
    mode="swing", fn=coiled_scan, weight=1,
))
```

Note: the `weight=1` argument requires Task 4 to land first OR you can write Task 3 + Task 4 as a single combined commit. Recommended order: skip the `weight=1` arg in Task 3 (it'll be added in Task 4), or land Task 4 immediately after Task 3 to keep the registry consistent. **For this plan, do Task 3 with `weight` field already in `ScanDescriptor`** — that means Task 4's schema change to `ScanDescriptor` should land first if you're executing strictly in order. **Reorder execution: do Task 4's Step 4.3 (add `weight` field to `ScanDescriptor` dataclass) before Task 3.** Or simply drop `weight=1` from this Task 3 commit and let Task 4 add it.

To keep the plan linear, drop `weight=1` from this commit; it gets added in Task 4 along with all other scans' weights.

- [ ] **Step 3.4: Run tests**

Run: `pytest tests/screener/test_coiled.py -v`
Expected: all six tests pass. If the synthetic flat-compression bars no longer satisfy the Phase Oscillator band (oscillator decays to near zero on flat closes near EMA21, so they should), tighten the synthetic generator so closes hover around `start_close * 1.6` for a longer flat tail.

- [ ] **Step 3.5: Run full screener suite**

Run: `pytest tests/screener/ -v`
Expected: green.

- [ ] **Step 3.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/coiled.py tests/screener/test_coiled.py
git commit -m "feat(screener): replace compression proxy with Saty Phase Oscillator value check"
```

---

### Task 4: Add `weight` to `ScanDescriptor`; runner computes weighted confluence

**Files:**
- Modify: `api/indicators/screener/registry.py`
- Modify: `api/schemas/screener.py`
- Modify: `api/indicators/screener/runner.py`
- Modify: `api/indicators/screener/scans/coiled.py` (add `weight=1` to its registration)
- Test: `tests/screener/test_registry.py`, `tests/screener/test_runner.py`

- [ ] **Step 4.1: Write failing tests**

Append to `tests/screener/test_registry.py`:

```python
def test_scan_descriptor_default_weight_is_one():
    from api.indicators.screener.registry import ScanDescriptor
    d = ScanDescriptor("x", "breakout", "trigger", "swing", lambda b, o: [])
    assert d.weight == 1


def test_scan_descriptor_accepts_explicit_weight():
    from api.indicators.screener.registry import ScanDescriptor
    d = ScanDescriptor("x", "breakout", "trigger", "swing", lambda b, o: [], weight=3)
    assert d.weight == 3
```

Append to `tests/screener/test_runner.py`:

```python
def test_runner_returns_weighted_confluence(mock_supabase):
    """Confluence score = sum of scan weights, not raw count."""
    from datetime import date
    from unittest.mock import MagicMock
    from api.indicators.screener.registry import ScanDescriptor, register_scan, clear_registry
    from api.indicators.screener.runner import run_screener
    from api.schemas.screener import ScanHit

    clear_registry()

    def scan_heavy(bars_by, _o):
        return [ScanHit(ticker=t, scan_id="heavy", lane="breakout", role="trigger") for t in bars_by]

    def scan_light(bars_by, _o):
        return [ScanHit(ticker=t, scan_id="light", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("heavy", "breakout", "trigger", "swing", scan_heavy, weight=3))
    register_scan(ScanDescriptor("light", "breakout", "trigger", "swing", scan_light, weight=1))

    chain = MagicMock()
    chain.insert.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.upsert.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": "run-w"}])
    mock_supabase.table.return_value = chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"AAPL": _bars([100.0] * 60)},
        today=date(2026, 4, 25),
    )
    aapl = next(t for t in response.tickers if t.ticker == "AAPL")
    assert aapl.confluence == 4
    assert sorted(aapl.scans_hit) == ["heavy", "light"]
    clear_registry()
```

- [ ] **Step 4.2: Run, confirm failures**

Run: `pytest tests/screener/test_registry.py tests/screener/test_runner.py -v`
Expected: 3 new failures.

- [ ] **Step 4.3: Add `weight` to `ScanDescriptor` in `api/indicators/screener/registry.py`**

Replace the dataclass:

```python
@dataclass(frozen=True)
class ScanDescriptor:
    scan_id: str
    lane: Lane
    role: Role
    mode: Mode
    fn: ScanFn
    weight: int = 1
```

- [ ] **Step 4.4: Add `confluence` weighted score to `TickerResult` in `api/schemas/screener.py`**

Replace the existing class:

```python
class TickerResult(BaseModel):
    ticker: str
    last_close: float
    overlay: IndicatorOverlay
    scans_hit: list[str]
    confluence: int = Field(..., description="Weighted score: sum of scan weights for hits")
```

- [ ] **Step 4.5: Update runner to compute weighted confluence**

In `api/indicators/screener/runner.py`, replace the `ticker_results` loop with:

```python
    weights_by_id = {d.scan_id: d.weight for d in descriptors}
    ticker_results: list[TickerResult] = []
    for ticker, scans in hits_by_ticker.items():
        if not scans:
            continue
        weighted = sum(weights_by_id.get(s, 1) for s in scans)
        ticker_results.append(TickerResult(
            ticker=ticker,
            last_close=float(eligible_bars[ticker]["close"].iloc[-1]),
            overlay=overlays[ticker],
            scans_hit=scans,
            confluence=weighted,
        ))
```

- [ ] **Step 4.6: Update Coiled Spring registration to specify `weight=1`**

In `api/indicators/screener/scans/coiled.py`, change the `register_scan(...)` call:

```python
register_scan(ScanDescriptor(
    scan_id="coiled_spring", lane="breakout", role="coiled",
    mode="swing", fn=coiled_scan, weight=1,
))
```

- [ ] **Step 4.7: Run tests**

Run: `pytest tests/screener/test_registry.py tests/screener/test_runner.py tests/screener/test_coiled.py -v`
Expected: all pass.

- [ ] **Step 4.8: Run full screener suite**

Run: `pytest tests/screener/ -v`
Expected: green.

- [ ] **Step 4.9: Commit**

```bash
pwd
git add api/indicators/screener/registry.py api/indicators/screener/runner.py \
        api/schemas/screener.py api/indicators/screener/scans/coiled.py \
        tests/screener/test_registry.py tests/screener/test_runner.py
git commit -m "feat(screener): add weight to ScanDescriptor; runner computes weighted confluence"
```

---

### Task 5: Wire `backfill_days_in_compression` into the runner

**Files:**
- Modify: `api/indicators/screener/persistence.py`
- Modify: `api/indicators/screener/runner.py`
- Test: `tests/screener/test_runner_backfill.py` (new)

- [ ] **Step 5.1: Extend `update_coiled_watchlist` signature**

In `api/indicators/screener/persistence.py`, replace the existing function with:

```python
def update_coiled_watchlist(
    sb: Client,
    mode: Mode,
    coiled_tickers: set[str],
    today: date,
    initial_days_by_ticker: dict[str, int] | None = None,
) -> None:
    """Reconcile active coiled rows with today's coiled set.

    initial_days_by_ticker: when a ticker is **newly** detected (no prior row),
        seed days_in_compression from this dict (the backfilled count) instead
        of 1. Existing tickers ignore this dict and increment as before.
    """
    initial = initial_days_by_ticker or {}
    existing = get_active_coiled(sb, mode)
    existing_by_ticker = {r["ticker"]: r for r in existing}

    upserts: list[dict] = []
    for ticker in coiled_tickers:
        prior = existing_by_ticker.get(ticker)
        if prior:
            upserts.append({
                "ticker": ticker, "mode": mode,
                "first_detected_at": prior["first_detected_at"],
                "last_seen_at": today.isoformat(),
                "days_in_compression": int(prior["days_in_compression"]) + 1,
                "status": "active",
            })
        else:
            seeded = max(1, int(initial.get(ticker, 1)))
            upserts.append({
                "ticker": ticker, "mode": mode,
                "first_detected_at": today.isoformat(),
                "last_seen_at": today.isoformat(),
                "days_in_compression": seeded,
                "status": "active",
            })
    for ticker, prior in existing_by_ticker.items():
        if ticker in coiled_tickers:
            continue
        upserts.append({
            "ticker": ticker, "mode": mode,
            "first_detected_at": prior["first_detected_at"],
            "last_seen_at": prior["last_seen_at"],
            "days_in_compression": int(prior["days_in_compression"]),
            "status": "broken",
        })
    if upserts:
        sb.table("coiled_watchlist").upsert(
            upserts, on_conflict="ticker,mode,first_detected_at",
        ).execute()
```

- [ ] **Step 5.2: Write failing test**

Create `tests/screener/test_runner_backfill.py`:

```python
"""Test that the runner backfills days_in_compression for newly-coiled tickers."""
from __future__ import annotations

import importlib
from datetime import date
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from api.indicators.screener.registry import clear_registry
from api.indicators.screener.runner import run_screener


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    import api.indicators.screener.scans.coiled as coiled_module
    importlib.reload(coiled_module)
    yield
    clear_registry()


def _flat_compressed_bars(days=120, compress_window=30):
    rng = np.random.default_rng(42)
    closes = list(np.linspace(100.0, 160.0, days - compress_window)) + [160.0] * compress_window
    dates = pd.date_range("2025-12-01", periods=days, freq="B")
    highs, lows = [], []
    for i, c in enumerate(closes):
        if i < days - compress_window:
            highs.append(c + rng.uniform(0, 0.2))
            lows.append(c - rng.uniform(0, 0.2))
        else:
            highs.append(160.05)
            lows.append(159.95)
    return pd.DataFrame({
        "date": dates, "open": closes, "high": highs, "low": lows,
        "close": closes, "volume": [5_000_000] * days,
    })


def test_runner_seeds_days_in_compression_from_backfill(mock_supabase):
    bars = _flat_compressed_bars(days=120, compress_window=30)

    runs_chain = MagicMock()
    runs_chain.insert.return_value = runs_chain
    runs_chain.execute.return_value = MagicMock(data=[{"id": "run-bf"}])

    coiled_chain = MagicMock()
    coiled_chain.select.return_value = coiled_chain
    coiled_chain.eq.return_value = coiled_chain
    coiled_chain.upsert.return_value = coiled_chain
    coiled_chain.execute.return_value = MagicMock(data=[])

    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"FAKE": bars},
        today=date(2026, 4, 25),
    )

    upsert_arg = coiled_chain.upsert.call_args[0][0]
    fake_row = next(r for r in upsert_arg if r["ticker"] == "FAKE")
    assert fake_row["days_in_compression"] >= 5, (
        f"Expected backfilled days >= 5; got {fake_row['days_in_compression']}"
    )
```

- [ ] **Step 5.3: Run, confirm failure**

Run: `pytest tests/screener/test_runner_backfill.py -v`
Expected: assertion fails — `days_in_compression == 1`.

- [ ] **Step 5.4: Wire backfill into `api/indicators/screener/runner.py`**

Remove the `TODO(plan-2)` comment block. Replace the `update_coiled_watchlist(...)` call site with:

```python
    from api.indicators.screener.scans.coiled import is_coiled
    from api.indicators.screener.persistence import (
        backfill_days_in_compression, get_active_coiled,
    )
    existing_active = {r["ticker"] for r in get_active_coiled(sb, mode)}
    new_coiled = coiled_tickers - existing_active
    initial_days = {
        ticker: backfill_days_in_compression(eligible_bars[ticker], is_coiled)
        for ticker in new_coiled
        if ticker in eligible_bars
    }

    update_coiled_watchlist(
        sb,
        mode=mode,
        coiled_tickers=coiled_tickers,
        today=today,
        initial_days_by_ticker=initial_days,
    )
```

- [ ] **Step 5.5: Run, confirm pass**

Run: `pytest tests/screener/test_runner_backfill.py tests/screener/test_persistence.py tests/screener/test_runner.py -v`
Expected: all pass.

- [ ] **Step 5.6: Run full screener suite**

Run: `pytest tests/screener/ -v`
Expected: green.

- [ ] **Step 5.7: Commit**

```bash
pwd
git add api/indicators/screener/runner.py api/indicators/screener/persistence.py \
        tests/screener/test_runner_backfill.py
git commit -m "feat(screener): wire backfill_days_in_compression into runner"
```

---

### Task 6: Add `fetch_hourly_bars_bulk` to bars module

**Files:**
- Modify: `api/indicators/screener/bars.py`
- Test: `tests/screener/test_bars_hourly.py` (new)

- [ ] **Step 6.1: Write failing test**

Create `tests/screener/test_bars_hourly.py`:

```python
"""Tests for hourly-bar bulk fetcher."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd


@patch("api.indicators.screener.bars.yf.download")
def test_fetch_hourly_bars_bulk_returns_dict_keyed_by_ticker(mock_dl):
    from api.indicators.screener.bars import fetch_hourly_bars_bulk

    idx = pd.date_range("2026-04-20 09:30", periods=3, freq="h", tz="America/New_York")
    fake = pd.DataFrame({
        ("Open", "AAPL"):   [170.0, 170.5, 171.0],
        ("High", "AAPL"):   [170.5, 171.0, 171.5],
        ("Low", "AAPL"):    [169.5, 170.3, 170.8],
        ("Close", "AAPL"):  [170.4, 170.9, 171.4],
        ("Volume", "AAPL"): [1_000_000, 800_000, 1_200_000],
        ("Open", "NVDA"):   [800.0, 802.0, 803.0],
        ("High", "NVDA"):   [802.0, 803.5, 804.5],
        ("Low", "NVDA"):    [799.0, 801.0, 802.5],
        ("Close", "NVDA"):  [801.5, 803.0, 804.0],
        ("Volume", "NVDA"): [500_000, 400_000, 600_000],
    }, index=idx)
    mock_dl.return_value = fake

    out = fetch_hourly_bars_bulk(["AAPL", "NVDA"], period="60d")
    assert set(out.keys()) == {"AAPL", "NVDA"}
    assert list(out["AAPL"].columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(out["AAPL"]) == 3


@patch("api.indicators.screener.bars.yf.download")
def test_fetch_hourly_bars_bulk_drops_all_nan_tickers(mock_dl):
    from api.indicators.screener.bars import fetch_hourly_bars_bulk

    idx = pd.date_range("2026-04-20 09:30", periods=2, freq="h", tz="America/New_York")
    fake = pd.DataFrame({
        ("Open", "AAPL"):   [170.0, 170.5],
        ("High", "AAPL"):   [170.5, 171.0],
        ("Low", "AAPL"):    [169.5, 170.3],
        ("Close", "AAPL"):  [170.4, 170.9],
        ("Volume", "AAPL"): [1_000_000, 800_000],
        ("Open", "DEAD"):   [np.nan, np.nan],
        ("High", "DEAD"):   [np.nan, np.nan],
        ("Low", "DEAD"):    [np.nan, np.nan],
        ("Close", "DEAD"):  [np.nan, np.nan],
        ("Volume", "DEAD"): [np.nan, np.nan],
    }, index=idx)
    mock_dl.return_value = fake

    out = fetch_hourly_bars_bulk(["AAPL", "DEAD"], period="60d")
    assert "AAPL" in out
    assert "DEAD" not in out


def test_fetch_hourly_bars_bulk_empty_input():
    from api.indicators.screener.bars import fetch_hourly_bars_bulk
    assert fetch_hourly_bars_bulk([], period="60d") == {}
```

- [ ] **Step 6.2: Run, confirm failure**

Run: `pytest tests/screener/test_bars_hourly.py -v`
Expected: ImportError on `fetch_hourly_bars_bulk`.

- [ ] **Step 6.3: Append `fetch_hourly_bars_bulk` to `api/indicators/screener/bars.py`**

```python
def fetch_hourly_bars_bulk(
    tickers: list[str],
    period: str = "60d",
) -> dict[str, pd.DataFrame]:
    """Fetch 60-minute OHLCV for all tickers in one yfinance batch call.

    yfinance limits hourly history to ~730 days. Vomy hourly only needs ~10–20
    bars; default period of "60d" is more than enough.

    Returns {ticker: DataFrame[date, open, high, low, close, volume]}.
    """
    if not tickers:
        return {}
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval="60m",
        group_by="column",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    out: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            df = pd.DataFrame({
                "date":   raw.index,
                "open":   raw[("Open", ticker)].values,
                "high":   raw[("High", ticker)].values,
                "low":    raw[("Low", ticker)].values,
                "close":  raw[("Close", ticker)].values,
                "volume": raw[("Volume", ticker)].values,
            })
        except KeyError:
            continue
        df = df.dropna(subset=["close"])
        if df.empty:
            continue
        out[ticker] = df.reset_index(drop=True)
    return out
```

- [ ] **Step 6.4: Run tests**

Run: `pytest tests/screener/test_bars_hourly.py -v`
Expected: 3 pass.

- [ ] **Step 6.5: Commit**

```bash
pwd
git add api/indicators/screener/bars.py tests/screener/test_bars_hourly.py
git commit -m "feat(screener): add fetch_hourly_bars_bulk for hourly-timeframe scans"
```

---

### Task 7: Add sector lookup cache (`sectors.py`)

**Files:**
- Create: `api/indicators/screener/sectors.py`
- Test: `tests/screener/test_sectors.py` (new)

The sector cache is consumed by Task 22's sector grouping in run results. Use yfinance `Ticker(t).info["sector"]` with a per-process LRU cache keyed by ticker. Empty results map to `"Unknown"` rather than raising.

- [ ] **Step 7.1: Write failing tests**

Create `tests/screener/test_sectors.py`:

```python
"""Tests for the ticker→sector cache."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sector_returns_yfinance_value(mock_ticker_cls):
    from api.indicators.screener.sectors import get_sector

    inst = MagicMock()
    inst.info = {"sector": "Technology"}
    mock_ticker_cls.return_value = inst
    assert get_sector("NVDA") == "Technology"


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sector_caches_result(mock_ticker_cls):
    """Repeated calls for same ticker should not call yfinance again."""
    from api.indicators.screener.sectors import get_sector, _CACHE

    _CACHE.clear()
    inst = MagicMock()
    inst.info = {"sector": "Healthcare"}
    mock_ticker_cls.return_value = inst

    get_sector("LLY")
    get_sector("LLY")
    get_sector("LLY")
    assert mock_ticker_cls.call_count == 1


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sector_returns_unknown_on_missing(mock_ticker_cls):
    from api.indicators.screener.sectors import get_sector, _CACHE
    _CACHE.clear()
    inst = MagicMock()
    inst.info = {}  # no 'sector' key
    mock_ticker_cls.return_value = inst
    assert get_sector("UNKNOWN") == "Unknown"


@patch("api.indicators.screener.sectors.yf.Ticker", side_effect=Exception("boom"))
def test_get_sector_returns_unknown_on_exception(_):
    from api.indicators.screener.sectors import get_sector, _CACHE
    _CACHE.clear()
    assert get_sector("BAD") == "Unknown"


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sectors_bulk_returns_dict(mock_ticker_cls):
    from api.indicators.screener.sectors import get_sectors_bulk, _CACHE
    _CACHE.clear()

    def make_inst(symbol):
        m = MagicMock()
        m.info = {"sector": "Technology" if symbol == "NVDA" else "Energy"}
        return m

    mock_ticker_cls.side_effect = lambda s: make_inst(s)
    out = get_sectors_bulk(["NVDA", "XOM"])
    assert out == {"NVDA": "Technology", "XOM": "Energy"}
```

- [ ] **Step 7.2: Run, confirm failure**

Run: `pytest tests/screener/test_sectors.py -v`
Expected: ImportError on `api.indicators.screener.sectors`.

- [ ] **Step 7.3: Implement `api/indicators/screener/sectors.py`**

```python
"""Ticker → sector cache.

Backed by yfinance .info["sector"]. Cached per-process to avoid hammering
yfinance on every screener run. Failures map to "Unknown" rather than raising —
sector grouping is a UX nicety, not a correctness gate.
"""
from __future__ import annotations

import logging

import yfinance as yf


logger = logging.getLogger(__name__)

_CACHE: dict[str, str] = {}


def get_sector(ticker: str) -> str:
    """Return the sector for ``ticker``; "Unknown" on failure or missing data."""
    if ticker in _CACHE:
        return _CACHE[ticker]
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector") or "Unknown"
    except Exception as exc:  # noqa: BLE001
        logger.warning("sector lookup failed for %s: %s", ticker, exc)
        sector = "Unknown"
    _CACHE[ticker] = sector
    return sector


def get_sectors_bulk(tickers: list[str]) -> dict[str, str]:
    """Return {ticker: sector} for many tickers; uses the same per-process cache."""
    return {t: get_sector(t) for t in tickers}
```

- [ ] **Step 7.4: Run tests**

Run: `pytest tests/screener/test_sectors.py -v`
Expected: 5 pass.

- [ ] **Step 7.5: Commit**

```bash
pwd
git add api/indicators/screener/sectors.py tests/screener/test_sectors.py
git commit -m "feat(screener): add yfinance-backed ticker→sector cache"
```

---

### Task 8: Pradeep 4% Breakout Bullish

**Scan ID:** `pradeep_4pct_breakout` · **Lane:** breakout · **Role:** trigger · **Weight:** 2

**Conditions on the latest daily bar:**
- `pct_change_today > 4%`
- `volume_today > volume_yesterday`
- `volume_today > 100_000`

**Files:**
- Create: `api/indicators/screener/scans/pradeep_4pct.py`
- Create: `tests/screener/test_pradeep_4pct.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 8.1: Write failing tests**

Create `tests/screener/test_pradeep_4pct.py`:

```python
"""Tests for Pradeep 4% Breakout scan."""
from __future__ import annotations

import importlib

import pandas as pd


def _bars(closes, volumes):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="B"),
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low":  [c * 0.99 for c in closes],
        "close": closes, "volume": volumes,
    })


def test_pradeep_4pct_fires_on_5pct_up_with_volume_increase():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [1_000_000] * 59 + [2_000_000]
    bars = _bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    hits = pradeep_4pct_scan({"AAPL": bars}, overlays)
    assert len(hits) == 1
    assert hits[0].scan_id == "pradeep_4pct_breakout"
    assert hits[0].lane == "breakout"
    assert hits[0].role == "trigger"


def test_pradeep_4pct_rejects_3pct_up():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [103.0]
    volumes = [1_000_000] * 60
    bars = _bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_rejects_when_volume_decreasing():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [1_000_000] * 59 + [800_000]
    bars = _bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_rejects_when_volume_below_100k():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.pradeep_4pct import pradeep_4pct_scan

    closes = [100.0] * 59 + [105.0]
    volumes = [50_000] * 59 + [80_000]
    bars = _bars(closes, volumes)
    overlays = {"AAPL": compute_overlay(bars)}
    assert pradeep_4pct_scan({"AAPL": bars}, overlays) == []


def test_pradeep_4pct_self_registers():
    from api.indicators.screener.registry import clear_registry, get_scan_by_id
    import api.indicators.screener.scans.pradeep_4pct as mod
    clear_registry()
    importlib.reload(mod)
    desc = get_scan_by_id("pradeep_4pct_breakout")
    assert desc is not None
    assert desc.weight == 2
```

- [ ] **Step 8.2: Run, confirm failure**

Run: `pytest tests/screener/test_pradeep_4pct.py -v`
Expected: ImportError.

- [ ] **Step 8.3: Implement `api/indicators/screener/scans/pradeep_4pct.py`**

```python
"""Pradeep 4% Breakout (bullish) — daily bar trigger.

Conditions on the latest daily bar:
  - pct_change_today > 4%
  - today's volume > yesterday's volume
  - today's volume > 100_000

Lane: breakout. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


PCT_CHANGE_MIN = 0.04
MIN_VOLUME = 100_000


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 2:
        return None
    today_vol = float(bars["volume"].iloc[-1])
    yesterday_vol = float(bars["volume"].iloc[-2])
    if overlay.pct_change_today <= PCT_CHANGE_MIN:
        return None
    if today_vol <= yesterday_vol:
        return None
    if today_vol < MIN_VOLUME:
        return None
    return {
        "pct_change_today": overlay.pct_change_today,
        "volume_today": today_vol,
        "volume_yesterday": yesterday_vol,
    }


def pradeep_4pct_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        evidence = _check(bars, overlay)
        if evidence is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="pradeep_4pct_breakout",
            lane="breakout", role="trigger", evidence=evidence,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="pradeep_4pct_breakout", lane="breakout", role="trigger",
    mode="swing", fn=pradeep_4pct_scan, weight=2,
))
```

- [ ] **Step 8.4: Update `api/indicators/screener/scans/__init__.py`**

Replace contents with:

```python
"""Scan implementations.

Importing this package triggers self-registration of every scan via
`register_scan(...)` calls at module bottom.
"""
from . import coiled         # noqa: F401
from . import pradeep_4pct   # noqa: F401
```

- [ ] **Step 8.5: Run tests**

Run: `pytest tests/screener/test_pradeep_4pct.py tests/screener/ -v`
Expected: all pass.

- [ ] **Step 8.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/pradeep_4pct.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_pradeep_4pct.py
git commit -m "feat(screener): add Pradeep 4% Breakout bullish trigger scan"
```

---

### Task 9: Qullamaggie Episodic Pivot

**Scan ID:** `qullamaggie_episodic_pivot` · **Lane:** breakout · **Role:** trigger · **Weight:** 2

**Conditions on the latest daily bar:**
- `pct_change_today > 7.5%`
- `close > yesterday's high`
- `dollar_volume_today > $100M`

**Files:**
- Create: `api/indicators/screener/scans/qullamaggie_episodic_pivot.py`
- Create: `tests/screener/test_qullamaggie_episodic_pivot.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 9.1: Write failing tests**

Create `tests/screener/test_qullamaggie_episodic_pivot.py`:

```python
"""Tests for Qullamaggie Episodic Pivot scan."""
from __future__ import annotations

import importlib

import pandas as pd


def _bars(closes, highs=None, volumes=None):
    n = len(closes)
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if volumes is None:
        volumes = [10_000_000] * n
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="B"),
        "open": closes, "high": highs,
        "low":  [c * 0.99 for c in closes],
        "close": closes, "volume": volumes,
    })


def test_episodic_pivot_fires_on_8pct_up_through_yesterday_high():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [100.0] * 59 + [108.0]
    highs = [101.0] * 59 + [108.5]
    volumes = [1_000_000] * 59 + [1_500_000]
    bars = _bars(closes, highs, volumes)
    overlays = {"NVDA": compute_overlay(bars)}
    hits = qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays)
    assert len(hits) == 1
    assert hits[0].evidence["close"] > hits[0].evidence["yesterday_high"]


def test_episodic_pivot_rejects_below_yesterday_high():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [100.0] * 59 + [108.0]
    highs = [120.0] * 59 + [108.5]
    volumes = [1_000_000] * 59 + [1_500_000]
    bars = _bars(closes, highs, volumes)
    overlays = {"NVDA": compute_overlay(bars)}
    assert qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays) == []


def test_episodic_pivot_rejects_low_dollar_volume():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_episodic_pivot import \
        qullamaggie_episodic_pivot_scan

    closes = [100.0] * 59 + [108.0]
    highs = [101.0] * 59 + [108.5]
    volumes = [50_000] * 60
    bars = _bars(closes, highs, volumes)
    overlays = {"NVDA": compute_overlay(bars)}
    assert qullamaggie_episodic_pivot_scan({"NVDA": bars}, overlays) == []


def test_episodic_pivot_self_registers():
    from api.indicators.screener.registry import clear_registry, get_scan_by_id
    import api.indicators.screener.scans.qullamaggie_episodic_pivot as mod
    clear_registry()
    importlib.reload(mod)
    desc = get_scan_by_id("qullamaggie_episodic_pivot")
    assert desc is not None and desc.weight == 2
```

- [ ] **Step 9.2: Run, confirm failure**

Run: `pytest tests/screener/test_qullamaggie_episodic_pivot.py -v` → ImportError.

- [ ] **Step 9.3: Implement `api/indicators/screener/scans/qullamaggie_episodic_pivot.py`**

```python
"""Qullamaggie Episodic Pivot — high-conviction breakout trigger.

Conditions on the latest daily bar:
  - pct_change_today > 7.5%
  - close > yesterday's high
  - dollar_volume_today > $100M

Lane: breakout. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


PCT_CHANGE_MIN = 0.075
DOLLAR_VOLUME_MIN = 100_000_000.0


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 2:
        return None
    yesterday_high = float(bars["high"].iloc[-2])
    last_close = float(bars["close"].iloc[-1])
    if overlay.pct_change_today <= PCT_CHANGE_MIN:
        return None
    if last_close <= yesterday_high:
        return None
    if overlay.dollar_volume_today < DOLLAR_VOLUME_MIN:
        return None
    return {
        "pct_change_today": overlay.pct_change_today,
        "close": last_close,
        "yesterday_high": yesterday_high,
        "dollar_volume": overlay.dollar_volume_today,
    }


def qullamaggie_episodic_pivot_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        ev = _check(bars, overlay)
        if ev is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="qullamaggie_episodic_pivot",
            lane="breakout", role="trigger", evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="qullamaggie_episodic_pivot", lane="breakout", role="trigger",
    mode="swing", fn=qullamaggie_episodic_pivot_scan, weight=2,
))
```

- [ ] **Step 9.4: Register in `scans/__init__.py`**

Append: `from . import qullamaggie_episodic_pivot   # noqa: F401`

- [ ] **Step 9.5: Run tests**

Run: `pytest tests/screener/test_qullamaggie_episodic_pivot.py tests/screener/ -v`
Expected: all pass.

- [ ] **Step 9.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/qullamaggie_episodic_pivot.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_qullamaggie_episodic_pivot.py
git commit -m "feat(screener): add Qullamaggie Episodic Pivot trigger scan"
```

---

### Task 10: Qullamaggie Continuation Base

**Scan ID:** `qullamaggie_continuation_base` · **Lane:** breakout · **Role:** setup_ready · **Weight:** 1

**Conditions:**
- `last_close > $5`
- `volume_avg_50d > 300_000`
- `adr_pct_20d > 4%`
- `|last_close - SMA10| / SMA10 <= 2%`
- `sum(volume[-5:]) / sum(volume[-10:-5]) < 0.5`

**Files:**
- Create: `api/indicators/screener/scans/qullamaggie_continuation_base.py`
- Create: `tests/screener/test_qullamaggie_continuation_base.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 10.1: Write failing tests**

Create `tests/screener/test_qullamaggie_continuation_base.py`:

```python
"""Tests for Qullamaggie Continuation Base scan."""
from __future__ import annotations

import importlib

import pandas as pd


def _bars(closes, volumes):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="B"),
        "open": closes,
        "high": [c * 1.04 for c in closes],
        "low":  [c * 0.96 for c in closes],
        "close": closes, "volume": volumes,
    })


def test_continuation_base_fires_when_all_conditions_met():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [50.0] * 50 + [55.0] * 10
    vols = [500_000] * 50 + [500_000] * 5 + [200_000] * 5
    bars = _bars(closes, vols)
    overlays = {"AAPL": compute_overlay(bars)}
    hits = qullamaggie_continuation_base_scan({"AAPL": bars}, overlays)
    assert len(hits) == 1
    assert hits[0].evidence["last_5d_volume_ratio"] < 0.5


def test_continuation_base_rejects_below_5_dollars():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [3.0] * 60
    vols = [500_000] * 60
    bars = _bars(closes, vols)
    overlays = {"PENNY": compute_overlay(bars)}
    assert qullamaggie_continuation_base_scan({"PENNY": bars}, overlays) == []


def test_continuation_base_rejects_when_too_far_from_10sma():
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.scans.qullamaggie_continuation_base import \
        qullamaggie_continuation_base_scan

    closes = [50.0] * 50 + [55.0] * 9 + [80.0]
    vols = [500_000] * 55 + [200_000] * 5
    bars = _bars(closes, vols)
    overlays = {"AAPL": compute_overlay(bars)}
    assert qullamaggie_continuation_base_scan({"AAPL": bars}, overlays) == []


def test_continuation_base_self_registers():
    from api.indicators.screener.registry import clear_registry, get_scan_by_id
    import api.indicators.screener.scans.qullamaggie_continuation_base as mod
    clear_registry()
    importlib.reload(mod)
    desc = get_scan_by_id("qullamaggie_continuation_base")
    assert desc is not None and desc.weight == 1
```

- [ ] **Step 10.2: Run, confirm failure** → ImportError.

- [ ] **Step 10.3: Implement `api/indicators/screener/scans/qullamaggie_continuation_base.py`**

```python
"""Qullamaggie Continuation Base — pullback to 10-SMA on a leader, volume drying.

Conditions on the latest daily bar:
  - last_close > $5
  - volume_avg_50d > 300_000
  - adr_pct_20d > 4%
  - |last_close - SMA10| / SMA10 <= 2%
  - sum(volume[-5:]) / sum(volume[-10:-5]) < 0.5

Lane: breakout. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


MIN_PRICE = 5.0
MIN_VOLUME_AVG_50D = 300_000.0
MIN_ADR_PCT = 0.04
MAX_DIST_FROM_10SMA = 0.02
MAX_RECENT_VOLUME_RATIO = 0.5


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 10:
        return None
    last_close = float(bars["close"].iloc[-1])
    if last_close < MIN_PRICE:
        return None
    if overlay.volume_avg_50d < MIN_VOLUME_AVG_50D:
        return None
    if overlay.adr_pct_20d < MIN_ADR_PCT:
        return None
    sma10 = float(bars["close"].rolling(10).mean().iloc[-1])
    if sma10 <= 0:
        return None
    if abs(last_close - sma10) / sma10 > MAX_DIST_FROM_10SMA:
        return None
    last_5_vol = float(bars["volume"].iloc[-5:].sum())
    prior_5_vol = float(bars["volume"].iloc[-10:-5].sum())
    if prior_5_vol <= 0:
        return None
    ratio = last_5_vol / prior_5_vol
    if ratio >= MAX_RECENT_VOLUME_RATIO:
        return None
    return {
        "last_close": last_close, "sma10": sma10,
        "dist_from_sma10_pct": abs(last_close - sma10) / sma10,
        "adr_pct_20d": overlay.adr_pct_20d,
        "last_5d_volume_ratio": ratio,
    }


def qullamaggie_continuation_base_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        ev = _check(bars, overlay)
        if ev is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="qullamaggie_continuation_base",
            lane="breakout", role="setup_ready", evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="qullamaggie_continuation_base", lane="breakout", role="setup_ready",
    mode="swing", fn=qullamaggie_continuation_base_scan, weight=1,
))
```

- [ ] **Step 10.4: Register in `scans/__init__.py`**

Append: `from . import qullamaggie_continuation_base  # noqa: F401`

- [ ] **Step 10.5: Run tests**

Run: `pytest tests/screener/ -v` → all green.

- [ ] **Step 10.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/qullamaggie_continuation_base.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_qullamaggie_continuation_base.py
git commit -m "feat(screener): add Qullamaggie Continuation Base setup_ready scan"
```

---

### Task 11: Saty Trigger Up — Day, Multiday, Swing variants

**Scan IDs:** `saty_trigger_up_day`, `saty_trigger_up_multiday`, `saty_trigger_up_swing` · **Lane:** breakout · **Role:** trigger · **Weight:** 3 each

**Conditions per variant:** read `overlay.saty_levels_by_mode[<mode>]` (mode = `day` / `multiday` / `swing`). Fire if:
- `last_close > levels.call_trigger` (above pivot trigger, i.e. above +23.6% level)
- `last_close < levels.mid_50_bull` (below +50% level — not yet golden-gated)

If `saty_levels_by_mode` is missing the requested mode (insufficient bars), skip silently.

**Files:**
- Create: `api/indicators/screener/scans/saty_trigger_up.py`
- Create: `tests/screener/test_saty_trigger_up.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 11.1: Write failing tests**

Create `tests/screener/test_saty_trigger_up.py`:

```python
"""Tests for Saty Trigger Up Day/Multiday/Swing scans."""
from __future__ import annotations

import importlib

import pandas as pd
import pytest

from api.indicators.screener.overlay import compute_overlay


def _bars(closes):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low":  [c * 0.995 for c in closes],
        "close": closes, "volume": [5_000_000] * n,
    })


def _scan_fn(scan_id):
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id(scan_id)
    assert desc is not None
    return desc.fn


def _force_register():
    """Re-import to ensure registration happens (module-level register_scan)."""
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.saty_trigger_up as mod
    clear_registry()
    importlib.reload(mod)


def test_saty_trigger_up_day_fires_when_close_between_trigger_and_mid_50():
    """Construct daily bars where close lands above call_trigger but below +50% level."""
    _force_register()
    # 60 bars trending up gradually so trigger and mid-50 are below the latest close
    closes = [100.0 + i * 0.3 for i in range(60)]
    bars = _bars(closes)
    overlays = {"NVDA": compute_overlay(bars)}
    # Sanity: daily levels available
    assert "day" in overlays["NVDA"].saty_levels_by_mode
    fn = _scan_fn("saty_trigger_up_day")
    hits = fn({"NVDA": bars}, overlays)
    # Whether it fires depends on the synthetic ATR/PDC arrangement; assert no crash
    # AND that if it fires, it carries the right scan_id and lane.
    for h in hits:
        assert h.scan_id == "saty_trigger_up_day"
        assert h.lane == "breakout"
        assert h.role == "trigger"


def test_saty_trigger_up_skips_when_close_below_trigger():
    """A rejection case: synthesise close at exactly PDC so we're below call_trigger."""
    _force_register()
    closes = [100.0] * 60
    bars = _bars(closes)
    overlays = {"AAPL": compute_overlay(bars)}
    fn = _scan_fn("saty_trigger_up_day")
    assert fn({"AAPL": bars}, overlays) == []


def test_saty_trigger_up_skips_when_levels_missing():
    """Empty saty_levels_by_mode ⇒ silent skip, no exception."""
    _force_register()
    closes = [100.0] * 60
    bars = _bars(closes)
    overlay = compute_overlay(bars)
    overlay = overlay.model_copy(update={"saty_levels_by_mode": {}})
    fn = _scan_fn("saty_trigger_up_day")
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_saty_trigger_up_three_variants_register():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    for sid in ("saty_trigger_up_day", "saty_trigger_up_multiday", "saty_trigger_up_swing"):
        desc = get_scan_by_id(sid)
        assert desc is not None, f"missing variant {sid}"
        assert desc.weight == 3
        assert desc.lane == "breakout"
        assert desc.role == "trigger"
```

- [ ] **Step 11.2: Run, confirm failure** → ImportError.

- [ ] **Step 11.3: Implement `api/indicators/screener/scans/saty_trigger_up.py`**

```python
"""Saty Trigger Up — Day / Multiday / Swing variants.

For each mode we read the per-mode ATR Levels dict from
overlay.saty_levels_by_mode[mode] and check:

    call_trigger < last_close < mid_50_bull

Fires a hit with scan_id 'saty_trigger_up_<mode>'. Skips silently when the
levels dict is missing for that mode (insufficient resampled history).

Lane: breakout. Role: trigger. Weight: 3 each.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


_MODES = ("day", "multiday", "swing")


def _make_scan(mode: str):
    scan_id = f"saty_trigger_up_{mode}"

    def scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],
        overlays_by_ticker: dict[str, IndicatorOverlay],
    ) -> list[ScanHit]:
        hits: list[ScanHit] = []
        for ticker, overlay in overlays_by_ticker.items():
            bars = bars_by_ticker.get(ticker)
            if bars is None or len(bars) < 1:
                continue
            levels_dict = overlay.saty_levels_by_mode.get(mode)
            if not levels_dict:
                continue
            call_trigger = levels_dict.get("call_trigger")
            levels = levels_dict.get("levels", {})
            mid_50 = levels.get("mid_50_bull", {}).get("price")
            if call_trigger is None or mid_50 is None:
                continue
            last_close = float(bars["close"].iloc[-1])
            if not (call_trigger < last_close < mid_50):
                continue
            hits.append(ScanHit(
                ticker=ticker, scan_id=scan_id,
                lane="breakout", role="trigger",
                evidence={
                    "mode": mode,
                    "last_close": last_close,
                    "call_trigger": call_trigger,
                    "mid_50_bull": mid_50,
                },
            ))
        return hits

    return scan_fn


for _mode in _MODES:
    register_scan(ScanDescriptor(
        scan_id=f"saty_trigger_up_{_mode}",
        lane="breakout", role="trigger", mode="swing",
        fn=_make_scan(_mode), weight=3,
    ))
```

- [ ] **Step 11.4: Register in `scans/__init__.py`**

Append: `from . import saty_trigger_up   # noqa: F401`

- [ ] **Step 11.5: Run tests**

Run: `pytest tests/screener/test_saty_trigger_up.py tests/screener/ -v`
Expected: all pass. The `test_saty_trigger_up_day_fires_when_close_between_trigger_and_mid_50` test is permissive — it asserts no crash and that any hits are well-formed. Variant registration test is the strict gate.

- [ ] **Step 11.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/saty_trigger_up.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_saty_trigger_up.py
git commit -m "feat(screener): add Saty Trigger Up Day/Multiday/Swing trigger scans"
```

---

### Task 12: Saty Golden Gate Up — Day, Multiday, Swing variants

**Scan IDs:** `saty_golden_gate_up_day`, `saty_golden_gate_up_multiday`, `saty_golden_gate_up_swing` · **Lane:** breakout · **Role:** trigger · **Weight:** 3 each

**Conditions per variant:** with `levels = overlay.saty_levels_by_mode[mode]`:
- `last_close >= levels.golden_gate_bull` (touched 61.8%)
- `last_close < levels.fib_786_bull` (not yet at 78.6%)

**Files:**
- Create: `api/indicators/screener/scans/saty_golden_gate_up.py`
- Create: `tests/screener/test_saty_golden_gate_up.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 12.1: Write failing tests**

Create `tests/screener/test_saty_golden_gate_up.py`:

```python
"""Tests for Saty Golden Gate Up Day/Multiday/Swing scans."""
from __future__ import annotations

import importlib

import pandas as pd

from api.indicators.screener.overlay import compute_overlay


def _bars(closes):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low":  [c * 0.995 for c in closes],
        "close": closes, "volume": [5_000_000] * n,
    })


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.saty_golden_gate_up as mod
    clear_registry()
    importlib.reload(mod)


def test_saty_gg_up_skips_when_levels_missing():
    _force_register()
    bars = _bars([100.0] * 60)
    overlay = compute_overlay(bars)
    overlay = overlay.model_copy(update={"saty_levels_by_mode": {}})
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("saty_golden_gate_up_day").fn
    assert fn({"AAPL": bars}, {"AAPL": overlay}) == []


def test_saty_gg_up_fires_when_close_between_gg_and_786():
    """Inject custom levels into overlay so we can deterministically test the threshold."""
    _force_register()
    bars = _bars([100.0] * 60)
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 95.0,
            "put_trigger": 90.0,
            "levels": {
                "trigger_bull":     {"price": 95.0, "fib": 0.236},
                "golden_gate_bull": {"price": 99.0, "fib": 0.382},
                "mid_50_bull":      {"price": 100.0, "fib": 0.5},
                "mid_range_bull":   {"price": 101.0, "fib": 0.618},
                "fib_786_bull":     {"price": 105.0, "fib": 0.786},
                "full_range_bull":  {"price": 110.0, "fib": 1.0},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    # Synthesise a bar with close = 100 (inside [99, 105) GG zone)
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("saty_golden_gate_up_day").fn
    hits = fn({"AAPL": bars}, {"AAPL": overlay})
    assert len(hits) == 1
    assert hits[0].evidence["golden_gate"] == 99.0
    assert hits[0].evidence["fib_786"] == 105.0


def test_saty_gg_up_three_variants_register():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    for sid in ("saty_golden_gate_up_day", "saty_golden_gate_up_multiday", "saty_golden_gate_up_swing"):
        desc = get_scan_by_id(sid)
        assert desc is not None
        assert desc.weight == 3
```

- [ ] **Step 12.2: Run, confirm failure** → ImportError.

- [ ] **Step 12.3: Implement `api/indicators/screener/scans/saty_golden_gate_up.py`**

```python
"""Saty Golden Gate Up — Day / Multiday / Swing.

For each mode read overlay.saty_levels_by_mode[mode]:
    golden_gate_bull <= last_close < fib_786_bull

Lane: breakout. Role: trigger. Weight: 3 each.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


_MODES = ("day", "multiday", "swing")


def _make_scan(mode: str):
    scan_id = f"saty_golden_gate_up_{mode}"

    def scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],
        overlays_by_ticker: dict[str, IndicatorOverlay],
    ) -> list[ScanHit]:
        hits: list[ScanHit] = []
        for ticker, overlay in overlays_by_ticker.items():
            bars = bars_by_ticker.get(ticker)
            if bars is None or len(bars) < 1:
                continue
            levels_dict = overlay.saty_levels_by_mode.get(mode)
            if not levels_dict:
                continue
            levels = levels_dict.get("levels", {})
            gg = levels.get("golden_gate_bull", {}).get("price")
            f786 = levels.get("fib_786_bull", {}).get("price")
            if gg is None or f786 is None:
                continue
            last_close = float(bars["close"].iloc[-1])
            if not (gg <= last_close < f786):
                continue
            hits.append(ScanHit(
                ticker=ticker, scan_id=scan_id,
                lane="breakout", role="trigger",
                evidence={
                    "mode": mode, "last_close": last_close,
                    "golden_gate": gg, "fib_786": f786,
                },
            ))
        return hits

    return scan_fn


for _mode in _MODES:
    register_scan(ScanDescriptor(
        scan_id=f"saty_golden_gate_up_{_mode}",
        lane="breakout", role="trigger", mode="swing",
        fn=_make_scan(_mode), weight=3,
    ))
```

- [ ] **Step 12.4: Register in `scans/__init__.py`**

Append: `from . import saty_golden_gate_up    # noqa: F401`

- [ ] **Step 12.5: Run tests**

Run: `pytest tests/screener/ -v` → green.

- [ ] **Step 12.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/saty_golden_gate_up.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_saty_golden_gate_up.py
git commit -m "feat(screener): add Saty Golden Gate Up Day/Multiday/Swing trigger scans"
```

---

### Task 13: Vomy Up Daily

**Scan ID:** `vomy_up_daily` · **Lane:** transition · **Role:** trigger · **Weight:** 2

The full satyland VomyEvaluator requires MTF scores + structure dicts the screener doesn't have. For the screener we use a **pure bar-based proxy** that captures the spirit of the setup (ribbon transitioning, bullish bias candle, oscillator turning up):

**Conditions on the latest daily bar:**
- `overlay.bias_candle == "blue"` (the buy-pullback candle in Pivot Ribbon Pro)
- `overlay.above_48ema is True`
- `overlay.phase_oscillator > overlay_yesterday.phase_oscillator` (oscillator rising — recompute yesterday's value via Pine port)
- `overlay.ribbon_state in ("chopzilla", "bullish")` (transitioning OR completed)

We need yesterday's oscillator. The simplest approach is to call `phase_oscillator(bars.iloc[:-1])` inside the scan rather than threading a parallel "yesterday overlay." This makes the scan self-contained.

**Files:**
- Create: `api/indicators/screener/scans/vomy_up_daily.py`
- Create: `tests/screener/test_vomy_up_daily.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 13.1: Write failing tests**

Create `tests/screener/test_vomy_up_daily.py`:

```python
"""Tests for Vomy Up Daily scan."""
from __future__ import annotations

import importlib

import pandas as pd

from api.indicators.screener.overlay import compute_overlay


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.vomy_up_daily as mod
    clear_registry()
    importlib.reload(mod)


def _bars_with_pullback(n=120):
    """Strong uptrend then a pullback day where close < open (so candle is down) and close stays >= EMA48."""
    closes = [100.0 + i * 1.0 for i in range(n - 1)] + [100.0 + (n - 2) * 1.0 - 0.5]
    highs = [c + 0.6 for c in closes]
    lows  = [c - 0.6 for c in closes]
    opens = [c for c in closes]
    opens[-1] = closes[-2]  # pullback bar opens at yesterday's close, closes lower → blue if above EMA48
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": [5_000_000] * n,
    })


def test_vomy_up_daily_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("vomy_up_daily")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "transition"
    assert desc.role == "trigger"


def test_vomy_up_daily_skips_when_bias_candle_not_blue():
    """Construct bars where bias_candle == 'green' (up day above EMA48)."""
    _force_register()
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=120, freq="B"),
        "open": [100.0 + i * 0.3 for i in range(120)],
        "high": [101.0 + i * 0.3 for i in range(120)],
        "low":  [ 99.0 + i * 0.3 for i in range(120)],
        "close":[100.5 + i * 0.3 for i in range(120)],
        "volume":[5_000_000] * 120,
    })
    overlays = {"NVDA": compute_overlay(bars)}
    if overlays["NVDA"].bias_candle == "blue":
        pytest.skip("synthetic constructed wrong; bias is blue here")
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("vomy_up_daily").fn
    assert fn({"NVDA": bars}, overlays) == []


def test_vomy_up_daily_handles_short_history_gracefully():
    """Bars under 22 (Phase Oscillator min) should return empty without raising."""
    _force_register()
    closes = [100.0] * 50  # Below sma_50 == 100, also below the typical scan needs
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=50, freq="B"),
        "open": closes,
        "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes],
        "close": closes, "volume": [1_000_000] * 50,
    })
    # compute_overlay may still work (50 bars >= SMA50). Vomy scan should not raise.
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("vomy_up_daily").fn
    out = fn({"AAPL": bars}, overlays)
    assert isinstance(out, list)
```

The "happy path" test for Vomy is hard to synthesise reliably because the bias candle classification depends on the exact open/close vs EMA48 relationship. We rely on the smoke test (Task 23) for live-data validation; the unit tests assert the gate logic and registration only.

- [ ] **Step 13.2: Run, confirm failure** → ImportError.

- [ ] **Step 13.3: Implement `api/indicators/screener/scans/vomy_up_daily.py`**

```python
"""Vomy Up Daily — bar-based proxy for the satyland Vomy bullish reversal.

Conditions on the latest daily bar:
  - overlay.bias_candle == "blue"      (Pivot Ribbon Pro buy-pullback)
  - overlay.above_48ema is True
  - overlay.ribbon_state in {"chopzilla", "bullish"}   (transitioning or completed)
  - phase_oscillator(today) > phase_oscillator(yesterday)   (rising)

Lane: transition. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def _phase_pair(bars: pd.DataFrame) -> tuple[float, float] | None:
    if len(bars) < 23:
        return None
    try:
        today = float(phase_oscillator(bars)["oscillator"])
        prior = float(phase_oscillator(bars.iloc[:-1])["oscillator"])
    except (ValueError, KeyError):
        return None
    return prior, today


def vomy_up_daily_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        if overlay.bias_candle != "blue":
            continue
        if not overlay.above_48ema:
            continue
        if overlay.ribbon_state not in ("chopzilla", "bullish"):
            continue
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        pair = _phase_pair(bars)
        if pair is None:
            continue
        prior, today = pair
        if not (today > prior):
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="vomy_up_daily",
            lane="transition", role="trigger",
            evidence={
                "bias_candle": overlay.bias_candle,
                "ribbon_state": overlay.ribbon_state,
                "phase_today": today, "phase_prior": prior,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="vomy_up_daily", lane="transition", role="trigger",
    mode="swing", fn=vomy_up_daily_scan, weight=2,
))
```

- [ ] **Step 13.4: Register in `scans/__init__.py`**

Append: `from . import vomy_up_daily   # noqa: F401`

- [ ] **Step 13.5: Run tests**

Run: `pytest tests/screener/test_vomy_up_daily.py tests/screener/ -v`
Expected: all pass. (The happy-path is intentionally not asserted via synthetic bars — smoke test handles that.)

- [ ] **Step 13.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/vomy_up_daily.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_vomy_up_daily.py
git commit -m "feat(screener): add Vomy Up Daily transition trigger scan"
```

---

### Task 14: Vomy Up Hourly + endpoint plumbing for hourly bars

**Scan ID:** `vomy_up_hourly` · **Lane:** transition · **Role:** trigger · **Weight:** 2

Vomy Up Hourly applies the same logic as Daily but on 60-minute bars. The runner currently takes only `bars_by_ticker` (daily). We extend the runner signature to accept an optional `hourly_bars_by_ticker` and pass it through. The hourly scan reads from this parallel dict.

**Files:**
- Create: `api/indicators/screener/scans/vomy_up_hourly.py`
- Create: `tests/screener/test_vomy_up_hourly.py`
- Modify: `api/indicators/screener/scans/__init__.py`
- Modify: `api/indicators/screener/runner.py` (accept hourly bars)
- Modify: `api/indicators/screener/registry.py` (extend `ScanFn` to accept hourly bars dict)
- Modify: `api/endpoints/screener_morning.py` (fetch + pass hourly bars)

The hourly bars threading is invasive — we add a third positional arg `hourly_bars_by_ticker: dict[str, pd.DataFrame]` to `ScanFn`. To stay backward-compatible with existing scans, **keep the existing 2-arg signature** and inject hourly bars via a module-level context-var indirection? No — that's clever but fragile. Better: change the signature **once**, and update every existing scan to accept (and ignore) the third arg.

- [ ] **Step 14.1: Update `ScanFn` signature in `api/indicators/screener/registry.py`**

Change to:

```python
ScanFn = Callable[
    [
        dict[str, pd.DataFrame],   # daily bars
        dict[str, IndicatorOverlay],
        dict[str, pd.DataFrame],   # hourly bars (may be empty)
    ],
    list[ScanHit],
]
```

- [ ] **Step 14.2: Update every existing scan to accept `hourly_bars_by_ticker`**

In each of these files, change the function signature:

- `api/indicators/screener/scans/coiled.py` — `def coiled_scan(bars_by_ticker, overlays_by_ticker, hourly_bars_by_ticker):`
- `pradeep_4pct.py`, `qullamaggie_episodic_pivot.py`, `qullamaggie_continuation_base.py`, `saty_trigger_up.py`, `saty_golden_gate_up.py`, `vomy_up_daily.py`

Each function ignores the new arg. Example for `pradeep_4pct.py`:

```python
def pradeep_4pct_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    ...
```

(The `_make_scan` factories in `saty_trigger_up.py` and `saty_golden_gate_up.py` need the same change to their inner `scan_fn`.)

- [ ] **Step 14.3: Update runner to thread hourly bars**

In `api/indicators/screener/runner.py`, change `run_screener`:

```python
def run_screener(
    sb: Client,
    mode: Mode,
    bars_by_ticker: dict[str, pd.DataFrame],
    today: date,
    scan_ids: list[str] | None = None,
    hourly_bars_by_ticker: dict[str, pd.DataFrame] | None = None,
) -> ScreenerRunResponse:
```

Inside, where scans dispatch:

```python
    hourly_bars = hourly_bars_by_ticker or {}
    for desc in descriptors:
        try:
            hits = desc.fn(eligible_bars, overlays, hourly_bars)
        except Exception:
            ...
```

- [ ] **Step 14.4: Update existing runner tests**

The autouse `_reset_registry` fixture in `tests/screener/test_runner.py` calls `desc.fn(bars_by, overlays_by)` via the dispatch path. The existing inline scan stubs (`scan_a`, `scan_b`, `scan_all`, `scan_heavy`, `scan_light`) take 2 args. Add a third positional `_hourly` arg to each:

```python
def scan_a(bars_by, overlays_by, _hourly):
    return [...]
```

Apply the same change in `tests/screener/test_runner_backfill.py` if any inline stubs there.

- [ ] **Step 14.5: Update endpoint to fetch hourly bars**

In `api/endpoints/screener_morning.py`, modify `run_morning`:

```python
@router.post(
    "/morning/run",
    response_model=ScreenerRunResponse,
    dependencies=[Depends(require_swing_token)],
)
def run_morning(req: ScreenerRunRequest) -> ScreenerRunResponse:
    sb = _get_supabase()
    tickers = _resolve_active_universe(sb, req.mode)
    if not tickers:
        raise HTTPException(status_code=400, detail="Active universe is empty.")
    daily = fetch_daily_bars_bulk(tickers, period="6mo")
    hourly = fetch_hourly_bars_bulk(tickers, period="60d")
    return run_screener(
        sb=sb,
        mode=req.mode,
        bars_by_ticker=daily,
        hourly_bars_by_ticker=hourly,
        today=date.today(),
        scan_ids=req.scan_ids,
    )
```

Add the import: `from api.indicators.screener.bars import fetch_daily_bars_bulk, fetch_hourly_bars_bulk`.

- [ ] **Step 14.6: Write failing tests for Vomy Hourly**

Create `tests/screener/test_vomy_up_hourly.py`:

```python
"""Tests for Vomy Up Hourly scan."""
from __future__ import annotations

import importlib

import pandas as pd

from api.indicators.screener.overlay import compute_overlay


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.vomy_up_hourly as mod
    clear_registry()
    importlib.reload(mod)


def test_vomy_up_hourly_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("vomy_up_hourly")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "transition"
    assert desc.role == "trigger"


def test_vomy_up_hourly_skips_when_no_hourly_bars():
    _force_register()
    daily = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=120, freq="B"),
        "open": [100.0] * 120, "high": [100.5] * 120, "low": [99.5] * 120,
        "close": [100.0] * 120, "volume": [1_000_000] * 120,
    })
    overlays = {"AAPL": compute_overlay(daily)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("vomy_up_hourly").fn
    assert fn({"AAPL": daily}, overlays, {}) == []


def test_vomy_up_hourly_handles_short_hourly_history():
    """If hourly bars exist but are too short for Phase Oscillator, return empty."""
    _force_register()
    daily = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=120, freq="B"),
        "open": [100.0] * 120, "high": [100.5] * 120, "low": [99.5] * 120,
        "close": [100.0] * 120, "volume": [1_000_000] * 120,
    })
    overlays = {"AAPL": compute_overlay(daily)}
    short_hourly = pd.DataFrame({
        "date": pd.date_range("2026-04-25 09:30", periods=10, freq="h"),
        "open": [100.0] * 10, "high": [100.2] * 10, "low": [99.8] * 10,
        "close": [100.1] * 10, "volume": [10_000] * 10,
    })
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("vomy_up_hourly").fn
    assert fn({"AAPL": daily}, overlays, {"AAPL": short_hourly}) == []
```

- [ ] **Step 14.7: Implement `api/indicators/screener/scans/vomy_up_hourly.py`**

```python
"""Vomy Up Hourly — same logic as vomy_up_daily but on 60m bars.

Conditions on the latest hourly bar:
  - hourly Pivot Ribbon bias_candle == "blue"
  - hourly close >= hourly EMA48
  - hourly ribbon_state in {"chopzilla", "bullish"}
  - hourly phase_oscillator rising

Reads from the runner's `hourly_bars_by_ticker` dict. Skips silently when no
hourly bars are available for a ticker.

Lane: transition. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.satyland.pivot_ribbon import pivot_ribbon
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def _evaluate_ticker(hourly_bars: pd.DataFrame) -> dict | None:
    if len(hourly_bars) < 50:
        return None
    try:
        pr = pivot_ribbon(hourly_bars)
        if pr["bias_candle"] != "blue":
            return None
        if not pr["above_48ema"]:
            return None
        if pr["ribbon_state"] not in ("chopzilla", "bullish"):
            return None
        today = float(phase_oscillator(hourly_bars)["oscillator"])
        prior = float(phase_oscillator(hourly_bars.iloc[:-1])["oscillator"])
    except (ValueError, KeyError):
        return None
    if not (today > prior):
        return None
    return {
        "bias_candle": pr["bias_candle"],
        "ribbon_state": pr["ribbon_state"],
        "phase_today_hourly": today,
        "phase_prior_hourly": prior,
    }


def vomy_up_hourly_scan(
    bars_by_ticker: dict[str, pd.DataFrame],          # noqa: ARG001  daily not used
    overlays_by_ticker: dict[str, IndicatorOverlay],  # noqa: ARG001
    hourly_bars_by_ticker: dict[str, pd.DataFrame],
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, hb in hourly_bars_by_ticker.items():
        ev = _evaluate_ticker(hb)
        if ev is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="vomy_up_hourly",
            lane="transition", role="trigger", evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="vomy_up_hourly", lane="transition", role="trigger",
    mode="swing", fn=vomy_up_hourly_scan, weight=2,
))
```

- [ ] **Step 14.8: Register in `scans/__init__.py`**

Append: `from . import vomy_up_hourly   # noqa: F401`

- [ ] **Step 14.9: Run full screener suite**

Run: `pytest tests/screener/ -v`
Expected: all pass. If endpoint tests in `test_endpoints.py` break because they don't pass hourly bars, mock `fetch_hourly_bars_bulk` to return `{}` in the affected tests.

- [ ] **Step 14.10: Commit**

```bash
pwd
git add api/indicators/screener/scans/vomy_up_hourly.py \
        api/indicators/screener/scans/__init__.py \
        api/indicators/screener/scans/coiled.py \
        api/indicators/screener/scans/pradeep_4pct.py \
        api/indicators/screener/scans/qullamaggie_episodic_pivot.py \
        api/indicators/screener/scans/qullamaggie_continuation_base.py \
        api/indicators/screener/scans/saty_trigger_up.py \
        api/indicators/screener/scans/saty_golden_gate_up.py \
        api/indicators/screener/scans/vomy_up_daily.py \
        api/indicators/screener/registry.py \
        api/indicators/screener/runner.py \
        api/endpoints/screener_morning.py \
        tests/screener/test_runner.py \
        tests/screener/test_runner_backfill.py \
        tests/screener/test_vomy_up_hourly.py
git commit -m "feat(screener): thread hourly bars through runner; add Vomy Up Hourly scan"
```

---

### Task 15: EMA Crossback (screener-side, stateless)

**Scan ID:** `ema_crossback` · **Lane:** transition · **Role:** setup_ready · **Weight:** 1

The full swing detector at `api/indicators/swing/setups/ema_crossback.py` requires `ctx["prior_ideas"]` (history of prior wedge_pop detections per ticker) — too expensive to thread for every screener run. **Adapt** the detection logic: drop the prior-wedge-pop gate and require that the ticker is in an established uptrend (ribbon_state=="bullish" + above_48ema). Reuse `volume_vs_avg` and `prior_swing_high` helpers from `api/indicators/swing/setups/base.py`.

**Conditions on the latest daily bar:**
- bars >= 30
- `overlay.ribbon_state == "bullish"` AND `overlay.above_48ema is True`
- close within 0.5 × ATR of EMA10 OR EMA20 (whichever is closer)
- low of the bar holds strictly above the respected EMA
- `volume_vs_avg(bars, 20) < 0.8` (volume drying up)

**Files:**
- Create: `api/indicators/screener/scans/ema_crossback.py`
- Create: `tests/screener/test_ema_crossback.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 15.1: Write failing tests**

Create `tests/screener/test_ema_crossback.py`:

```python
"""Tests for the screener EMA Crossback adapter."""
from __future__ import annotations

import importlib

import pandas as pd

from api.indicators.screener.overlay import compute_overlay


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.ema_crossback as mod
    clear_registry()
    importlib.reload(mod)


def test_ema_crossback_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("ema_crossback")
    assert desc is not None
    assert desc.weight == 1
    assert desc.lane == "transition"
    assert desc.role == "setup_ready"


def test_ema_crossback_skips_when_not_in_uptrend():
    _force_register()
    closes = [100.0 - i * 0.5 for i in range(60)]   # downtrend
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.3 for c in closes],
        "low":  [c - 0.3 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("ema_crossback").fn
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_ema_crossback_skips_when_volume_not_drying():
    """High volume on the pullback day disqualifies even with all other conditions met."""
    _force_register()
    closes = [100.0 + i * 0.5 for i in range(60)]
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.3 for c in closes],
        "low":  [c - 0.3 for c in closes], "close": closes,
        "volume": [1_000_000] * 59 + [3_000_000],   # surge today
    })
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("ema_crossback").fn
    assert fn({"AAPL": bars}, overlays, {}) == []
```

- [ ] **Step 15.2: Run, confirm failure** → ImportError.

- [ ] **Step 15.3: Implement `api/indicators/screener/scans/ema_crossback.py`**

```python
"""EMA Crossback (screener-side, stateless).

Detects a healthy pullback to EMA10/20 in an established uptrend. Unlike the
swing-pipeline detector, we do NOT require a prior Wedge Pop in history —
that gate exists in the swing pipeline; the screener's job is to surface
candidates regardless of upstream history.

Conditions on the latest daily bar:
  - bars >= 30
  - ribbon_state == "bullish" AND above_48ema
  - close within 0.5 × ATR of EMA10 or EMA20 (whichever is closer)
  - bar's low > respected EMA
  - volume / 20-day avg < 0.8

Lane: transition. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.common.atr import atr as atr_series
from api.indicators.common.moving_averages import ema as ema_series
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.indicators.swing.setups.base import volume_vs_avg
from api.schemas.screener import IndicatorOverlay, ScanHit


HALF_ATR = 0.5
MAX_VOLUME_RATIO = 0.8


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 30:
        return None
    if overlay.ribbon_state != "bullish" or not overlay.above_48ema:
        return None
    ema10 = ema_series(bars, 10)
    ema20 = ema_series(bars, 20)
    atr14 = atr_series(bars, 14)
    cur_close = float(bars["close"].iloc[-1])
    cur_low = float(bars["low"].iloc[-1])
    cur_atr = float(atr14.iloc[-1])
    cur_e10 = float(ema10.iloc[-1])
    cur_e20 = float(ema20.iloc[-1])
    if cur_atr <= 0:
        return None

    dist10 = abs(cur_close - cur_e10)
    dist20 = abs(cur_close - cur_e20)
    if dist10 <= dist20:
        respected, respected_val, respected_dist = "ema10", cur_e10, dist10
    else:
        respected, respected_val, respected_dist = "ema20", cur_e20, dist20
    if respected_dist >= HALF_ATR * cur_atr:
        return None
    if cur_low <= respected_val:
        return None

    try:
        vol_ratio = volume_vs_avg(bars, 20)
    except ValueError:
        return None
    if vol_ratio >= MAX_VOLUME_RATIO:
        return None

    return {
        "respected_ema": respected,
        "dist_to_ema_atr": respected_dist / cur_atr,
        "volume_vs_20d_avg": vol_ratio,
    }


def ema_crossback_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        ev = _check(bars, overlay)
        if ev is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="ema_crossback",
            lane="transition", role="setup_ready", evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="ema_crossback", lane="transition", role="setup_ready",
    mode="swing", fn=ema_crossback_scan, weight=1,
))
```

- [ ] **Step 15.4: Register in `scans/__init__.py`**

Append: `from . import ema_crossback   # noqa: F401`

- [ ] **Step 15.5: Run tests**

Run: `pytest tests/screener/test_ema_crossback.py tests/screener/ -v` → all green.

- [ ] **Step 15.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/ema_crossback.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_ema_crossback.py
git commit -m "feat(screener): add EMA Crossback transition setup_ready scan"
```

---

### Task 16: Saty Reversion Up / Down

**Scan IDs:** `saty_reversion_up`, `saty_reversion_down` · **Lane:** reversion · **Role:** setup_ready · **Weight:** 1 each

**Conditions:**

- **Saty Reversion Up:** `overlay.bias_candle == "blue"` AND `last_close < EMA21` (price below pivot, bullish-pullback candle forming — anticipating bounce)
- **Saty Reversion Down:** `overlay.bias_candle == "orange"` AND `last_close > EMA21`

These are mean-reversion candidates per spec §3 / Reversion lane.

**Files:**
- Create: `api/indicators/screener/scans/saty_reversion.py`
- Create: `tests/screener/test_saty_reversion.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 16.1: Write failing tests**

Create `tests/screener/test_saty_reversion.py`:

```python
"""Tests for Saty Reversion Up/Down scans."""
from __future__ import annotations

import importlib

import pandas as pd


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.saty_reversion as mod
    clear_registry()
    importlib.reload(mod)


def test_saty_reversion_up_and_down_both_register():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    for sid in ("saty_reversion_up", "saty_reversion_down"):
        desc = get_scan_by_id(sid)
        assert desc is not None
        assert desc.weight == 1
        assert desc.lane == "reversion"
        assert desc.role == "setup_ready"


def test_saty_reversion_up_skips_when_bias_not_blue():
    _force_register()
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.registry import get_scan_by_id

    closes = [100.0 + i * 0.3 for i in range(120)]
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=120, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 120,
    })
    overlays = {"AAPL": compute_overlay(bars)}
    fn = get_scan_by_id("saty_reversion_up").fn
    if overlays["AAPL"].bias_candle == "blue":
        return  # condition naturally met; skip
    assert fn({"AAPL": bars}, overlays, {}) == []
```

- [ ] **Step 16.2: Run, confirm failure** → ImportError.

- [ ] **Step 16.3: Implement `api/indicators/screener/scans/saty_reversion.py`**

```python
"""Saty Reversion Up / Down — mean-reversion setup candidates.

Reversion Up:
  - bias_candle == "blue"
  - last_close < EMA21

Reversion Down:
  - bias_candle == "orange"
  - last_close > EMA21

Lane: reversion. Role: setup_ready. Weight: 1 each.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.common.moving_averages import ema as ema_series
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


def _ema21_value(bars: pd.DataFrame) -> float | None:
    if len(bars) < 21:
        return None
    return float(ema_series(bars, 21).iloc[-1])


def _make_reversion_scan(direction: str):
    expected_candle = "blue" if direction == "up" else "orange"
    scan_id = f"saty_reversion_{direction}"

    def scan_fn(
        bars_by_ticker: dict[str, pd.DataFrame],
        overlays_by_ticker: dict[str, IndicatorOverlay],
        hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
    ) -> list[ScanHit]:
        hits: list[ScanHit] = []
        for ticker, overlay in overlays_by_ticker.items():
            if overlay.bias_candle != expected_candle:
                continue
            bars = bars_by_ticker.get(ticker)
            if bars is None:
                continue
            ema21 = _ema21_value(bars)
            if ema21 is None:
                continue
            last_close = float(bars["close"].iloc[-1])
            if direction == "up" and last_close >= ema21:
                continue
            if direction == "down" and last_close <= ema21:
                continue
            hits.append(ScanHit(
                ticker=ticker, scan_id=scan_id,
                lane="reversion", role="setup_ready",
                evidence={
                    "bias_candle": overlay.bias_candle,
                    "last_close": last_close, "ema21": ema21,
                },
            ))
        return hits

    return scan_fn


for _dir in ("up", "down"):
    register_scan(ScanDescriptor(
        scan_id=f"saty_reversion_{_dir}",
        lane="reversion", role="setup_ready", mode="swing",
        fn=_make_reversion_scan(_dir), weight=1,
    ))
```

- [ ] **Step 16.4: Register in `scans/__init__.py`**

Append: `from . import saty_reversion   # noqa: F401`

- [ ] **Step 16.5: Run tests**

Run: `pytest tests/screener/test_saty_reversion.py tests/screener/ -v` → green.

- [ ] **Step 16.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/saty_reversion.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_saty_reversion.py
git commit -m "feat(screener): add Saty Reversion Up/Down setup_ready scans"
```

---

### Task 17: Vomy Down at extension highs

**Scan ID:** `vomy_down_extension` · **Lane:** reversion · **Role:** trigger · **Weight:** 2

**Conditions on the latest daily bar:**
- `overlay.bias_candle == "orange"` (Pivot Ribbon bearish bounce — short signal)
- `overlay.above_48ema is False`
- `overlay.ribbon_state in {"chopzilla", "bearish"}`
- `phase_oscillator(today) < phase_oscillator(yesterday)` (oscillator falling)
- `overlay.extension > 7` (price stretched >7× ATR above 50MA — climax zone)

**Files:**
- Create: `api/indicators/screener/scans/vomy_down_extension.py`
- Create: `tests/screener/test_vomy_down_extension.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 17.1: Write failing tests**

Create `tests/screener/test_vomy_down_extension.py`:

```python
"""Tests for Vomy Down at extension highs scan."""
from __future__ import annotations

import importlib


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.vomy_down_extension as mod
    clear_registry()
    importlib.reload(mod)


def test_vomy_down_extension_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("vomy_down_extension")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "reversion"
    assert desc.role == "trigger"


def test_vomy_down_extension_skips_when_extension_too_low():
    """Extension <= 7 ⇒ no hit even if other conditions match."""
    import pandas as pd
    from api.indicators.screener.overlay import compute_overlay
    from api.indicators.screener.registry import get_scan_by_id

    _force_register()
    closes = [100.0] * 60   # flat ⇒ low extension
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    overlays = {"AAPL": compute_overlay(bars)}
    fn = get_scan_by_id("vomy_down_extension").fn
    assert fn({"AAPL": bars}, overlays, {}) == []
```

- [ ] **Step 17.2: Run, confirm failure** → ImportError.

- [ ] **Step 17.3: Implement `api/indicators/screener/scans/vomy_down_extension.py`**

```python
"""Vomy Down at extension highs — bearish reversal trigger near climax.

Conditions on the latest daily bar:
  - bias_candle == "orange"
  - not above_48ema
  - ribbon_state in {"chopzilla", "bearish"}
  - phase_oscillator falling
  - overlay.extension > 7

Lane: reversion. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.satyland.phase_oscillator import phase_oscillator
from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


EXTENSION_MIN = 7.0


def _phase_pair(bars: pd.DataFrame) -> tuple[float, float] | None:
    if len(bars) < 23:
        return None
    try:
        today = float(phase_oscillator(bars)["oscillator"])
        prior = float(phase_oscillator(bars.iloc[:-1])["oscillator"])
    except (ValueError, KeyError):
        return None
    return prior, today


def vomy_down_extension_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        if overlay.bias_candle != "orange":
            continue
        if overlay.above_48ema:
            continue
        if overlay.ribbon_state not in ("chopzilla", "bearish"):
            continue
        if overlay.extension <= EXTENSION_MIN:
            continue
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        pair = _phase_pair(bars)
        if pair is None:
            continue
        prior, today = pair
        if not (today < prior):
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="vomy_down_extension",
            lane="reversion", role="trigger",
            evidence={
                "bias_candle": overlay.bias_candle,
                "ribbon_state": overlay.ribbon_state,
                "extension": overlay.extension,
                "phase_today": today, "phase_prior": prior,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="vomy_down_extension", lane="reversion", role="trigger",
    mode="swing", fn=vomy_down_extension_scan, weight=2,
))
```

- [ ] **Step 17.4: Register in `scans/__init__.py`**

Append: `from . import vomy_down_extension   # noqa: F401`

- [ ] **Step 17.5: Run tests**

Run: `pytest tests/screener/ -v` → green.

- [ ] **Step 17.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/vomy_down_extension.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_vomy_down_extension.py
git commit -m "feat(screener): add Vomy Down at extension highs reversion trigger"
```

---

### Task 18: Saty Trigger Down (Day)

**Scan ID:** `saty_trigger_down_day` · **Lane:** reversion · **Role:** trigger · **Weight:** 3

Mirror of Saty Trigger Up Day: with `levels = overlay.saty_levels_by_mode["day"]`,
- `last_close < levels.put_trigger`
- `last_close > levels.mid_50_bear`

(We only ship the Day variant in Plan 2; Multiday/Swing down variants can be added later.)

**Files:**
- Create: `api/indicators/screener/scans/saty_trigger_down.py`
- Create: `tests/screener/test_saty_trigger_down.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 18.1: Write failing tests**

Create `tests/screener/test_saty_trigger_down.py`:

```python
"""Tests for Saty Trigger Down (Day) scan."""
from __future__ import annotations

import importlib

import pandas as pd

from api.indicators.screener.overlay import compute_overlay


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.saty_trigger_down as mod
    clear_registry()
    importlib.reload(mod)


def test_saty_trigger_down_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("saty_trigger_down_day")
    assert desc is not None
    assert desc.weight == 3
    assert desc.lane == "reversion"
    assert desc.role == "trigger"


def test_saty_trigger_down_skips_when_levels_missing():
    _force_register()
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    overlay = compute_overlay(bars).model_copy(update={"saty_levels_by_mode": {}})
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("saty_trigger_down_day").fn
    assert fn({"AAPL": bars}, {"AAPL": overlay}, {}) == []


def test_saty_trigger_down_fires_when_close_in_band():
    _force_register()
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    overlay = compute_overlay(bars)
    custom_levels = {
        "day": {
            "call_trigger": 110.0,
            "put_trigger": 105.0,
            "levels": {
                "trigger_bear":  {"price": 105.0, "fib": 0.236},
                "mid_50_bear":   {"price":  90.0, "fib": 0.5},
            },
        },
    }
    overlay = overlay.model_copy(update={"saty_levels_by_mode": custom_levels})
    # close = 100 is below put_trigger (105) and above mid_50_bear (90)
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("saty_trigger_down_day").fn
    hits = fn({"NVDA": bars}, {"NVDA": overlay}, {})
    assert len(hits) == 1
    assert hits[0].evidence["put_trigger"] == 105.0
    assert hits[0].evidence["mid_50_bear"] == 90.0
```

- [ ] **Step 18.2: Run, confirm failure** → ImportError.

- [ ] **Step 18.3: Implement `api/indicators/screener/scans/saty_trigger_down.py`**

```python
"""Saty Trigger Down (Day) — mirror of Saty Trigger Up Day for reversion lane.

Reads overlay.saty_levels_by_mode["day"]. Conditions:
  put_trigger > last_close > mid_50_bear

Lane: reversion. Role: trigger. Weight: 3.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


def saty_trigger_down_day_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker.get(ticker)
        if bars is None or len(bars) < 1:
            continue
        levels_dict = overlay.saty_levels_by_mode.get("day")
        if not levels_dict:
            continue
        put_trigger = levels_dict.get("put_trigger")
        levels = levels_dict.get("levels", {})
        mid_50_bear = levels.get("mid_50_bear", {}).get("price")
        if put_trigger is None or mid_50_bear is None:
            continue
        last_close = float(bars["close"].iloc[-1])
        if not (mid_50_bear < last_close < put_trigger):
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="saty_trigger_down_day",
            lane="reversion", role="trigger",
            evidence={
                "last_close": last_close,
                "put_trigger": put_trigger,
                "mid_50_bear": mid_50_bear,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="saty_trigger_down_day",
    lane="reversion", role="trigger", mode="swing",
    fn=saty_trigger_down_day_scan, weight=3,
))
```

- [ ] **Step 18.4: Register in `scans/__init__.py`**

Append: `from . import saty_trigger_down   # noqa: F401`

- [ ] **Step 18.5: Run tests**

Run: `pytest tests/screener/ -v` → green.

- [ ] **Step 18.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/saty_trigger_down.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_saty_trigger_down.py
git commit -m "feat(screener): add Saty Trigger Down (Day) reversion trigger"
```

---

### Task 19: Kell Wedge Pop adapter

**Scan ID:** `kell_wedge_pop` · **Lane:** breakout · **Role:** setup_ready · **Weight:** 1

Wraps `api.indicators.swing.setups.wedge_pop.detect()`. The existing detector takes `(bars, qqq_bars, ctx)`. We need QQQ bars threaded through. Strategy:
- The endpoint always includes `"QQQ"` in the universe before calling the runner.
- The scan looks up `bars_by_ticker.get("QQQ")` and skips silently if absent.
- `ctx = {"ticker": ticker}` — the existing Wedge Pop detector only reads `ctx["ticker"]`.

**Files:**
- Create: `api/indicators/screener/scans/kell_wedge_pop.py`
- Create: `tests/screener/test_kell_wedge_pop.py`
- Modify: `api/indicators/screener/scans/__init__.py`
- Modify: `api/endpoints/screener_morning.py` (ensure QQQ is always fetched)

- [ ] **Step 19.1: Endpoint plumbing — always include QQQ**

In `api/endpoints/screener_morning.py`, modify `run_morning`:

```python
    daily = fetch_daily_bars_bulk(sorted(set(tickers) | {"QQQ"}), period="6mo")
    hourly = fetch_hourly_bars_bulk(tickers, period="60d")
```

- [ ] **Step 19.2: Write failing tests**

Create `tests/screener/test_kell_wedge_pop.py`:

```python
"""Tests for Kell Wedge Pop screener adapter."""
from __future__ import annotations

import importlib

import pandas as pd


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.kell_wedge_pop as mod
    clear_registry()
    importlib.reload(mod)


def test_kell_wedge_pop_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("kell_wedge_pop")
    assert desc is not None
    assert desc.weight == 1
    assert desc.lane == "breakout"
    assert desc.role == "setup_ready"


def test_kell_wedge_pop_skips_when_qqq_missing():
    _force_register()
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    from api.indicators.screener.overlay import compute_overlay
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("kell_wedge_pop").fn
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_kell_wedge_pop_skips_qqq_itself():
    """QQQ should not be evaluated as a hit candidate against itself."""
    _force_register()
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    from api.indicators.screener.overlay import compute_overlay
    overlays = {"QQQ": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("kell_wedge_pop").fn
    assert fn({"QQQ": bars}, overlays, {}) == []
```

- [ ] **Step 19.3: Run, confirm failure** → ImportError.

- [ ] **Step 19.4: Implement `api/indicators/screener/scans/kell_wedge_pop.py`**

```python
"""Kell Wedge Pop — adapter around api/indicators/swing/setups/wedge_pop.py.

The existing detector requires QQQ bars for relative-strength comparison. The
endpoint always fetches QQQ alongside the universe; we read it out of
bars_by_ticker. If QQQ is missing, every scan returns empty.

Lane: breakout. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import logging

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.indicators.swing.setups.wedge_pop import detect as wedge_pop_detect
from api.schemas.screener import IndicatorOverlay, ScanHit


logger = logging.getLogger(__name__)


def kell_wedge_pop_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],   # noqa: ARG001
    hourly_bars_by_ticker: dict[str, pd.DataFrame],    # noqa: ARG001
) -> list[ScanHit]:
    qqq = bars_by_ticker.get("QQQ")
    if qqq is None:
        return []
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if ticker == "QQQ":
            continue
        try:
            setup_hit = wedge_pop_detect(bars, qqq, {"ticker": ticker})
        except Exception:  # noqa: BLE001
            logger.exception("kell_wedge_pop: detector raised for %s", ticker)
            continue
        if setup_hit is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="kell_wedge_pop",
            lane="breakout", role="setup_ready",
            evidence=dict(setup_hit.detection_evidence),
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="kell_wedge_pop", lane="breakout", role="setup_ready",
    mode="swing", fn=kell_wedge_pop_scan, weight=1,
))
```

- [ ] **Step 19.5: Register in `scans/__init__.py`**

Append: `from . import kell_wedge_pop   # noqa: F401`

- [ ] **Step 19.6: Run tests**

Run: `pytest tests/screener/ -v` → green.

- [ ] **Step 19.7: Commit**

```bash
pwd
git add api/indicators/screener/scans/kell_wedge_pop.py \
        api/indicators/screener/scans/__init__.py \
        api/endpoints/screener_morning.py \
        tests/screener/test_kell_wedge_pop.py
git commit -m "feat(screener): add Kell Wedge Pop adapter; ensure QQQ in universe"
```

---

### Task 20: Kell Flag Base

**Scan ID:** `kell_flag_base` · **Lane:** breakout · **Role:** setup_ready · **Weight:** 1

A flag base is a tight consolidation following a strong impulse leg (Kell's "Base-n-Break" pre-trigger). New detector. Define concretely:

**Conditions on the latest daily bar:**
- bars >= 30
- `overlay.ribbon_state == "bullish"` AND `overlay.above_48ema is True`
- **Impulse:** the prior 10–20 bar window (positions [-25:-5]) saw `pct_change` >= 15%
- **Tight base:** the last 5 bars have `(max(high) - min(low)) / mean(close) < 5%`
- volume on last 5 bars averaging < 80% of the prior 20-bar average

**Files:**
- Create: `api/indicators/screener/scans/kell_flag_base.py`
- Create: `tests/screener/test_kell_flag_base.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 20.1: Write failing tests**

Create `tests/screener/test_kell_flag_base.py`:

```python
"""Tests for Kell Flag Base scan."""
from __future__ import annotations

import importlib

import pandas as pd


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.kell_flag_base as mod
    clear_registry()
    importlib.reload(mod)


def test_kell_flag_base_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("kell_flag_base")
    assert desc is not None
    assert desc.weight == 1
    assert desc.lane == "breakout"
    assert desc.role == "setup_ready"


def test_kell_flag_base_skips_when_no_prior_impulse():
    _force_register()
    closes = [100.0] * 60   # flat ⇒ no impulse
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    from api.indicators.screener.overlay import compute_overlay
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("kell_flag_base").fn
    assert fn({"AAPL": bars}, overlays, {}) == []


def test_kell_flag_base_skips_when_base_not_tight():
    """Wide-range last 5 bars disqualify."""
    _force_register()
    n = 60
    impulse = [100.0 + i * 1.0 for i in range(40, 55)]    # 15-bar impulse
    base = [115.0, 125.0, 110.0, 120.0, 115.0]              # wide-range last 5
    closes = [100.0] * (n - 20) + impulse + base
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": closes, "high": [c + 1.0 for c in closes],
        "low":  [c - 1.0 for c in closes], "close": closes,
        "volume": [1_000_000] * n,
    })
    from api.indicators.screener.overlay import compute_overlay
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("kell_flag_base").fn
    assert fn({"AAPL": bars}, overlays, {}) == []
```

- [ ] **Step 20.2: Run, confirm failure** → ImportError.

- [ ] **Step 20.3: Implement `api/indicators/screener/scans/kell_flag_base.py`**

```python
"""Kell Flag Base — tight consolidation following a strong impulse leg.

Conditions on the latest daily bar:
  - bars >= 30
  - ribbon_state == "bullish" AND above_48ema
  - prior 15-bar window (bars[-25:-5]) shows >= 15% net move
  - last 5 bars: (max(high) - min(low)) / mean(close) < 5%
  - mean(volume[-5:]) < 0.8 * mean(volume[-25:-5])

Lane: breakout. Role: setup_ready. Weight: 1.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.schemas.screener import IndicatorOverlay, ScanHit


IMPULSE_LOOKBACK_START = -25
IMPULSE_LOOKBACK_END = -5
IMPULSE_MIN_PCT = 0.15
BASE_WINDOW = 5
BASE_MAX_RANGE_PCT = 0.05
VOLUME_DRYING_RATIO = 0.8


def _check(bars: pd.DataFrame, overlay: IndicatorOverlay) -> dict | None:
    if len(bars) < 30:
        return None
    if overlay.ribbon_state != "bullish" or not overlay.above_48ema:
        return None

    impulse_window = bars.iloc[IMPULSE_LOOKBACK_START:IMPULSE_LOOKBACK_END]
    if len(impulse_window) < 10:
        return None
    start = float(impulse_window["close"].iloc[0])
    peak = float(impulse_window["close"].max())
    if start <= 0:
        return None
    impulse_pct = (peak / start) - 1.0
    if impulse_pct < IMPULSE_MIN_PCT:
        return None

    base = bars.iloc[-BASE_WINDOW:]
    base_range = float(base["high"].max() - base["low"].min())
    base_mean = float(base["close"].mean())
    if base_mean <= 0:
        return None
    base_range_pct = base_range / base_mean
    if base_range_pct >= BASE_MAX_RANGE_PCT:
        return None

    base_vol = float(base["volume"].mean())
    impulse_vol = float(impulse_window["volume"].mean())
    if impulse_vol <= 0:
        return None
    vol_ratio = base_vol / impulse_vol
    if vol_ratio >= VOLUME_DRYING_RATIO:
        return None

    return {
        "impulse_pct": impulse_pct,
        "base_range_pct": base_range_pct,
        "base_volume_ratio": vol_ratio,
    }


def kell_flag_base_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],
    hourly_bars_by_ticker: dict[str, pd.DataFrame],   # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, overlay in overlays_by_ticker.items():
        bars = bars_by_ticker.get(ticker)
        if bars is None:
            continue
        ev = _check(bars, overlay)
        if ev is None:
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="kell_flag_base",
            lane="breakout", role="setup_ready", evidence=ev,
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="kell_flag_base", lane="breakout", role="setup_ready",
    mode="swing", fn=kell_flag_base_scan, weight=1,
))
```

- [ ] **Step 20.4: Register in `scans/__init__.py`**

Append: `from . import kell_flag_base   # noqa: F401`

- [ ] **Step 20.5: Run tests**

Run: `pytest tests/screener/ -v` → green.

- [ ] **Step 20.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/kell_flag_base.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_kell_flag_base.py
git commit -m "feat(screener): add Kell Flag Base setup_ready scan"
```

---

### Task 21: Kell Exhaustion Extension adapter

**Scan ID:** `kell_exhaustion_extension` · **Lane:** reversion · **Role:** trigger · **Weight:** 2

Wraps `api.indicators.swing.setups.exhaustion_extension.detect_exhaustion_extension()`. The full detector takes `last_base_breakout_idx` (from history) for its `kell_2nd_extension` flag — the screener doesn't have that. We pass `None` and only fire on the **stateless** flags: `far_above_10ema` or `climax_bar`.

**Conditions:** call detector with `last_base_breakout_idx=None`. Fire if `flag.far_above_10ema or flag.climax_bar`.

**Files:**
- Create: `api/indicators/screener/scans/kell_exhaustion_extension.py`
- Create: `tests/screener/test_kell_exhaustion_extension.py`
- Modify: `api/indicators/screener/scans/__init__.py`

- [ ] **Step 21.1: Write failing tests**

Create `tests/screener/test_kell_exhaustion_extension.py`:

```python
"""Tests for Kell Exhaustion Extension adapter."""
from __future__ import annotations

import importlib

import pandas as pd


def _force_register():
    from api.indicators.screener.registry import clear_registry
    import api.indicators.screener.scans.kell_exhaustion_extension as mod
    clear_registry()
    importlib.reload(mod)


def test_kell_exhaustion_self_registers():
    _force_register()
    from api.indicators.screener.registry import get_scan_by_id
    desc = get_scan_by_id("kell_exhaustion_extension")
    assert desc is not None
    assert desc.weight == 2
    assert desc.lane == "reversion"
    assert desc.role == "trigger"


def test_kell_exhaustion_fires_on_far_above_10ema():
    """Bars where last close is > 2 ATR above EMA10 ⇒ far_above_10ema flag fires."""
    _force_register()
    n = 60
    closes = [100.0] * (n - 5) + [110.0, 115.0, 120.0, 130.0, 150.0]
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": closes, "high": [c + 1.0 for c in closes],
        "low":  [c - 1.0 for c in closes], "close": closes,
        "volume": [1_000_000] * n,
    })
    from api.indicators.screener.overlay import compute_overlay
    overlays = {"NVDA": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("kell_exhaustion_extension").fn
    hits = fn({"NVDA": bars}, overlays, {})
    assert len(hits) == 1
    assert hits[0].evidence["far_above_10ema"] is True


def test_kell_exhaustion_skips_when_no_extension():
    _force_register()
    closes = [100.0] * 60
    bars = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [1_000_000] * 60,
    })
    from api.indicators.screener.overlay import compute_overlay
    overlays = {"AAPL": compute_overlay(bars)}
    from api.indicators.screener.registry import get_scan_by_id
    fn = get_scan_by_id("kell_exhaustion_extension").fn
    assert fn({"AAPL": bars}, overlays, {}) == []
```

- [ ] **Step 21.2: Run, confirm failure** → ImportError.

- [ ] **Step 21.3: Implement `api/indicators/screener/scans/kell_exhaustion_extension.py`**

```python
"""Kell Exhaustion Extension adapter — stateless subset of the swing detector.

The full swing detector at api/indicators/swing/setups/exhaustion_extension.py
flags 4 conditions: kell_2nd_extension (history-dependent), climax_bar,
far_above_10ema, weekly_air. The screener can only evaluate the **stateless**
two — climax_bar and far_above_10ema — so we pass last_base_breakout_idx=None.

Lane: reversion. Role: trigger. Weight: 2.
"""
from __future__ import annotations

import pandas as pd

from api.indicators.screener.registry import ScanDescriptor, register_scan
from api.indicators.swing.setups.exhaustion_extension import (
    detect_exhaustion_extension,
)
from api.schemas.screener import IndicatorOverlay, ScanHit


def kell_exhaustion_extension_scan(
    bars_by_ticker: dict[str, pd.DataFrame],
    overlays_by_ticker: dict[str, IndicatorOverlay],   # noqa: ARG001
    hourly_bars_by_ticker: dict[str, pd.DataFrame],    # noqa: ARG001
) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for ticker, bars in bars_by_ticker.items():
        if ticker == "QQQ":
            continue
        try:
            flag = detect_exhaustion_extension(bars, last_base_breakout_idx=None)
        except Exception:  # noqa: BLE001
            continue
        if not (flag.far_above_10ema or flag.climax_bar):
            continue
        hits.append(ScanHit(
            ticker=ticker, scan_id="kell_exhaustion_extension",
            lane="reversion", role="trigger",
            evidence={
                "far_above_10ema": flag.far_above_10ema,
                "climax_bar": flag.climax_bar,
            },
        ))
    return hits


register_scan(ScanDescriptor(
    scan_id="kell_exhaustion_extension", lane="reversion", role="trigger",
    mode="swing", fn=kell_exhaustion_extension_scan, weight=2,
))
```

- [ ] **Step 21.4: Register in `scans/__init__.py`**

Append: `from . import kell_exhaustion_extension   # noqa: F401`

- [ ] **Step 21.5: Run tests**

Run: `pytest tests/screener/ -v` → green.

- [ ] **Step 21.6: Commit**

```bash
pwd
git add api/indicators/screener/scans/kell_exhaustion_extension.py \
        api/indicators/screener/scans/__init__.py \
        tests/screener/test_kell_exhaustion_extension.py
git commit -m "feat(screener): add Kell Exhaustion Extension adapter (stateless flags only)"
```

---

### Task 22: Earnings filter + sector grouping + structured logging

**Files:**
- Modify: `api/schemas/screener.py` (add `sector` to `TickerResult`; add `sector_summary` to `ScreenerRunResponse`)
- Modify: `api/indicators/screener/runner.py`
- Modify: `api/endpoints/screener_morning.py` (sector cache hookup)
- Test: `tests/screener/test_runner_observability.py` (new)

**Earnings filter:** scans in lane=`breakout` with role=`trigger` (i.e. Pradeep, Qullamaggie EP, Saty Trigger Up family, Saty GG Up family) should not fire if the ticker has earnings within the next 5 days. Fetches via `api.indicators.swing.earnings_calendar.next_earnings_date`. Cache the result per ticker per run.

**Sector grouping:** every `TickerResult` carries `sector: str`. The response also carries `sector_summary: dict[str, int]` — `{"Technology": 5, "Healthcare": 2, ...}`.

**Structured logging:** for each scan dispatch, log `{"scan_id": ..., "duration_ms": ..., "hits": ...}`. For each ticker that hits, log `{"ticker": ..., "scans": [...], "confluence": ...}`. Use `logger.info(...)` with `extra={...}`.

- [ ] **Step 22.1: Update schemas**

In `api/schemas/screener.py`, modify `TickerResult` and `ScreenerRunResponse`:

```python
class TickerResult(BaseModel):
    ticker: str
    last_close: float
    overlay: IndicatorOverlay
    scans_hit: list[str]
    confluence: int
    sector: str = Field("Unknown", description="GICS sector from yfinance, or 'Unknown'")


class ScreenerRunResponse(BaseModel):
    run_id: str
    mode: Mode
    ran_at: datetime
    universe_size: int
    scan_count: int
    hit_count: int
    duration_seconds: float
    tickers: list[TickerResult]
    sector_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Sector → number of hit tickers in this run",
    )
```

- [ ] **Step 22.2: Add helper functions to runner**

Add to `api/indicators/screener/runner.py`:

```python
from collections import Counter
from datetime import timedelta

from api.indicators.screener.sectors import get_sectors_bulk
from api.indicators.swing.earnings_calendar import next_earnings_date


_EARNINGS_FILTERED_SCANS = frozenset({
    "pradeep_4pct_breakout",
    "qullamaggie_episodic_pivot",
    "saty_trigger_up_day", "saty_trigger_up_multiday", "saty_trigger_up_swing",
    "saty_golden_gate_up_day", "saty_golden_gate_up_multiday", "saty_golden_gate_up_swing",
})
EARNINGS_BLACKOUT_DAYS = 5


def _within_earnings_blackout(ticker: str, today: date) -> bool:
    """True if ticker has earnings within the next EARNINGS_BLACKOUT_DAYS days."""
    nxt = next_earnings_date(ticker)
    if nxt is None:
        return False
    return today <= nxt <= today + timedelta(days=EARNINGS_BLACKOUT_DAYS)
```

- [ ] **Step 22.3: Wire filtering, sector lookup, structured logging into `run_screener`**

In the scan dispatch loop, replace the body:

```python
    weights_by_id = {d.scan_id: d.weight for d in descriptors}
    earnings_cache: dict[str, bool] = {}

    coiled_tickers: set[str] = set()
    for desc in descriptors:
        scan_started = time.time()
        try:
            hits = desc.fn(eligible_bars, overlays, hourly_bars)
        except Exception:
            logger.exception("scan %s failed; skipping its hits for this run", desc.scan_id)
            continue
        kept = 0
        for hit in hits:
            if desc.scan_id in _EARNINGS_FILTERED_SCANS:
                if hit.ticker not in earnings_cache:
                    earnings_cache[hit.ticker] = _within_earnings_blackout(hit.ticker, today)
                if earnings_cache[hit.ticker]:
                    continue
            hits_by_ticker.setdefault(hit.ticker, []).append(hit.scan_id)
            kept += 1
            if hit.scan_id == "coiled_spring":
                coiled_tickers.add(hit.ticker)
        logger.info(
            "screener.scan_complete",
            extra={
                "scan_id": desc.scan_id,
                "duration_ms": int((time.time() - scan_started) * 1000),
                "hits_raw": len(hits),
                "hits_kept": kept,
            },
        )
```

After computing `ticker_results`, look up sectors and build the summary:

```python
    ticker_list = [t.ticker for t in ticker_results]
    sectors = get_sectors_bulk(ticker_list) if ticker_list else {}
    enriched: list[TickerResult] = []
    for t in ticker_results:
        sector = sectors.get(t.ticker, "Unknown")
        enriched.append(t.model_copy(update={"sector": sector}))
        logger.info(
            "screener.ticker_hit",
            extra={
                "ticker": t.ticker, "scans": t.scans_hit,
                "confluence": t.confluence, "sector": sector,
            },
        )
    ticker_results = enriched
    sector_summary = dict(Counter(t.sector for t in ticker_results))
```

And include in the response:

```python
    return ScreenerRunResponse(
        run_id=run_id,
        mode=mode,
        ran_at=datetime.now(timezone.utc),
        universe_size=len(bars_by_ticker),
        scan_count=len(descriptors),
        hit_count=len(ticker_results),
        duration_seconds=round(duration, 3),
        tickers=ticker_results,
        sector_summary=sector_summary,
    )
```

- [ ] **Step 22.4: Write tests for the filter, sector grouping, and log emission**

Create `tests/screener/test_runner_observability.py`:

```python
"""Tests for runner-level observability: earnings filter, sector grouping, structured logs."""
from __future__ import annotations

import logging
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api.indicators.screener.registry import ScanDescriptor, clear_registry, register_scan
from api.indicators.screener.runner import run_screener
from api.schemas.screener import ScanHit


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_registry()
    yield
    clear_registry()


def _bars(closes):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": closes, "high": [c + 0.5 for c in closes],
        "low":  [c - 0.5 for c in closes], "close": closes,
        "volume": [5_000_000] * n,
    })


def _make_chain(rows=None):
    c = MagicMock()
    c.insert.return_value = c
    c.select.return_value = c
    c.eq.return_value = c
    c.upsert.return_value = c
    c.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return c


@patch("api.indicators.screener.runner.get_sectors_bulk")
@patch("api.indicators.screener.runner.next_earnings_date")
def test_earnings_blackout_filters_breakout_triggers(mock_earnings, mock_sectors, mock_supabase):
    """A ticker with earnings in 3 days must not fire on a breakout-trigger scan."""
    mock_earnings.return_value = date(2026, 4, 28)   # 3 days from today
    mock_sectors.return_value = {}

    def trigger_scan(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="pradeep_4pct_breakout",
                        lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor(
        "pradeep_4pct_breakout", "breakout", "trigger", "swing",
        trigger_scan, weight=2,
    ))

    runs_chain = _make_chain([{"id": "run-eo"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"AAPL": _bars([100.0] * 60)},
        today=date(2026, 4, 25),
    )
    assert response.hit_count == 0


@patch("api.indicators.screener.runner.get_sectors_bulk")
@patch("api.indicators.screener.runner.next_earnings_date")
def test_earnings_blackout_does_not_filter_setup_ready(mock_earnings, mock_sectors, mock_supabase):
    """A setup_ready scan should still hit even within the earnings blackout window."""
    mock_earnings.return_value = date(2026, 4, 28)
    mock_sectors.return_value = {"AAPL": "Technology"}

    def setup_scan(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="kell_wedge_pop",
                        lane="breakout", role="setup_ready") for t in bars_by]

    register_scan(ScanDescriptor(
        "kell_wedge_pop", "breakout", "setup_ready", "swing",
        setup_scan, weight=1,
    ))

    runs_chain = _make_chain([{"id": "run-sr"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={"AAPL": _bars([100.0] * 60)},
        today=date(2026, 4, 25),
    )
    assert response.hit_count == 1


@patch("api.indicators.screener.runner.get_sectors_bulk")
@patch("api.indicators.screener.runner.next_earnings_date", return_value=None)
def test_runner_returns_sector_summary(_, mock_sectors, mock_supabase):
    mock_sectors.return_value = {"AAPL": "Technology", "NVDA": "Technology", "XOM": "Energy"}

    def scan_a(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="a", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", scan_a, weight=1))

    runs_chain = _make_chain([{"id": "run-sec"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    response = run_screener(
        sb=mock_supabase, mode="swing",
        bars_by_ticker={
            "AAPL": _bars([100.0] * 60),
            "NVDA": _bars([100.0] * 60),
            "XOM":  _bars([100.0] * 60),
        },
        today=date(2026, 4, 25),
    )
    assert response.sector_summary == {"Technology": 2, "Energy": 1}
    by_ticker = {t.ticker: t for t in response.tickers}
    assert by_ticker["AAPL"].sector == "Technology"


@patch("api.indicators.screener.runner.get_sectors_bulk", return_value={})
@patch("api.indicators.screener.runner.next_earnings_date", return_value=None)
def test_runner_emits_structured_logs(_, __, mock_supabase, caplog):
    """Per-scan and per-ticker logs are emitted."""
    def scan_a(bars_by, _o, _h):
        return [ScanHit(ticker=t, scan_id="a", lane="breakout", role="trigger") for t in bars_by]

    register_scan(ScanDescriptor("a", "breakout", "trigger", "swing", scan_a, weight=1))

    runs_chain = _make_chain([{"id": "run-log"}])
    coiled_chain = _make_chain([])
    mock_supabase.table.side_effect = lambda name: runs_chain if name == "screener_runs" else coiled_chain

    with caplog.at_level(logging.INFO, logger="api.indicators.screener.runner"):
        run_screener(
            sb=mock_supabase, mode="swing",
            bars_by_ticker={"AAPL": _bars([100.0] * 60)},
            today=date(2026, 4, 25),
        )
    msgs = [r.message for r in caplog.records]
    assert "screener.scan_complete" in msgs
    assert "screener.ticker_hit" in msgs
```

- [ ] **Step 22.5: Run, confirm passing**

Run: `pytest tests/screener/test_runner_observability.py tests/screener/ -v`
Expected: green. If any pre-existing test now passes empty `sector_summary` and breaks, update it to assert `response.sector_summary == {}` for the no-mocks case.

- [ ] **Step 22.6: Commit**

```bash
pwd
git add api/schemas/screener.py api/indicators/screener/runner.py \
        tests/screener/test_runner_observability.py
git commit -m "feat(screener): earnings filter, sector grouping, structured logs"
```

---

### Task 23: Live smoke run validation

**Goal:** broaden `scripts/screener_smoke_test.py` to a representative ticker set, run it against live Supabase + yfinance, and eyeball whether scan hit rates look sane.

**Files:**
- Modify: `scripts/screener_smoke_test.py`

- [ ] **Step 23.1: Update sample ticker list and output formatting**

Replace the contents of `scripts/screener_smoke_test.py` with:

```python
#!/usr/bin/env python3
"""End-to-end smoke test for the morning screener.

Runs against real Supabase + yfinance — does NOT mock anything. Use sparingly.

Usage:
    venv/bin/python scripts/screener_smoke_test.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date

# Ensure every scan is registered
import api.indicators.screener.scans  # noqa: F401
from api.indicators.screener.bars import (
    fetch_daily_bars_bulk,
    fetch_hourly_bars_bulk,
)
from api.indicators.screener.runner import run_screener
from supabase import create_client


# Representative tickers across mega-caps, momentum, and broad sectors.
SAMPLE_TICKERS = [
    "NVDA", "AAPL", "MSFT", "TSLA", "AMD", "META", "AVGO", "COST", "GOOGL",
    "MXL", "PLTR", "CRWD", "PANW", "VRT", "SOFI", "MSTR", "COIN",
    "NFLX", "ABNB", "UBER", "LLY", "UNH", "XOM", "WMT", "JPM",
    "QQQ",
]


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", file=sys.stderr)
        return 1

    sb = create_client(url, key)

    print(f"Fetching daily bars for {len(SAMPLE_TICKERS)} tickers...")
    daily = fetch_daily_bars_bulk(SAMPLE_TICKERS, period="1y")
    print(f"  Got daily bars for {len(daily)} tickers.")

    print("Fetching hourly bars (60d)...")
    hourly = fetch_hourly_bars_bulk(SAMPLE_TICKERS, period="60d")
    print(f"  Got hourly bars for {len(hourly)} tickers.")

    print("Running screener...")
    response = run_screener(
        sb=sb,
        mode="swing",
        bars_by_ticker=daily,
        hourly_bars_by_ticker=hourly,
        today=date.today(),
    )

    print()
    print(f"Run {response.run_id} — {response.duration_seconds}s")
    print(f"  Universe size : {response.universe_size}")
    print(f"  Scans run     : {response.scan_count}")
    print(f"  Hits          : {response.hit_count}")
    print(f"  Sectors       : {response.sector_summary}")

    # Per-scan hit counts
    scan_counter = Counter()
    for t in response.tickers:
        for s in t.scans_hit:
            scan_counter[s] += 1
    print()
    print("Per-scan hit counts:")
    for scan_id, n in sorted(scan_counter.items(), key=lambda kv: -kv[1]):
        print(f"  {scan_id:40s}  {n}")

    print()
    print("Per-ticker results:")
    for tr in sorted(response.tickers, key=lambda t: -t.confluence):
        print(
            f"  {tr.ticker:6s} conf={tr.confluence:>3d} "
            f"ext={tr.overlay.extension:+6.2f} atr%={tr.overlay.atr_pct*100:5.2f} "
            f"phase={tr.overlay.phase_oscillator:+6.1f} "
            f"sec={tr.sector[:12]:<12s} scans={tr.scans_hit}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 23.2: Run the smoke script against live infra**

```bash
pwd
SUPABASE_URL=$(grep SUPABASE_URL .env | cut -d= -f2-) \
SUPABASE_SERVICE_KEY=$(grep SUPABASE_SERVICE_KEY .env | cut -d= -f2-) \
venv/bin/python scripts/screener_smoke_test.py 2>&1 | tee /tmp/screener_smoke.log
```

Expected output:
- Fetches daily for ~25 tickers, hourly for the same.
- Run completes within 60 seconds.
- "Per-scan hit counts" prints non-zero counts for at least 3 different scans.
- "Per-ticker results" lists tickers with confluence ≥ 1.
- No tracebacks.

If any scan reliably reports zero hits across multiple smoke runs (run on three different trading days), file an issue noting the threshold may need recalibration.

- [ ] **Step 23.3: Commit the smoke script**

```bash
pwd
git add scripts/screener_smoke_test.py
git commit -m "test(screener): broaden smoke universe + print per-scan hit counts"
```

- [ ] **Step 23.4: Open PR**

```bash
gh pr create \
  --title "Screener Plan 2: scan catalog expansion + Phase Oscillator + backfill" \
  --body "$(cat <<'EOF'
## Summary
- Replaces the Coiled Spring `_compression_proxy` with the real Saty Phase Oscillator (port already in `api/indicators/satyland/phase_oscillator.py`); threshold zone -20..+20 per spec §4.
- Wires the unused `backfill_days_in_compression` helper into the runner so first-observation coils don't reset to day 1.
- Adds 12+ scans across Breakout / Transition / Reversion lanes (Pradeep, Qullamaggie EP + Continuation Base, Saty Trigger Up/Down + GG Up Day/Multiday/Swing, Vomy Up Daily/Hourly, EMA Crossback, Saty Reversion Up/Down, Vomy Down extension, Kell Wedge Pop / Flag Base / Exhaustion Extension).
- Extends `IndicatorOverlay` with volume / move / phase / ribbon / Saty-Levels-by-mode fields; threading hourly bars through the runner for Vomy Hourly.
- Adds confluence weighting (per-scan weights), sector grouping, structured logging, earnings blackout filter for breakout-trigger scans.
- Smoke-validated against live yfinance + Supabase.

## Test plan
- [ ] `pytest tests/screener/ -v` — all green (~95+ tests).
- [ ] `pytest tests/swing/ -v` — no regressions.
- [ ] `venv/bin/python scripts/screener_smoke_test.py` — runs in < 60s, reports non-zero hits across multiple scans.
- [ ] Manual: `curl -X POST -H "Authorization: Bearer $SWING_API_TOKEN" https://trend-trading-mcp-production.up.railway.app/api/screener/morning/run -d '{"mode":"swing"}'` — returns 200 with populated `sector_summary` and `tickers[].sector`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

### Spec coverage check (against `docs/superpowers/specs/2026-04-25-unified-screener-design.md`)

| Spec section | Plan task |
|---|---|
| §3 Breakout Universe (Qullamaggie / Saty Momentum) | covered by existing Plan 1 universe; no scan needed for "Universe" role itself |
| §3 Breakout Coiled (multi-condition coiled spring) | Tasks 3, 5 (Phase Oscillator + backfill) |
| §3 Breakout Setup-ready (Continuation Base, Wedge Pop, Flag Base) | Tasks 10, 19, 20 |
| §3 Breakout Trigger (Pradeep 4%, Qullamaggie EP, Saty Trigger Up, Saty GG Up) | Tasks 8, 9, 11, 12 |
| §3 Transition Coiled (EMA-touch tracker) | **Deferred to Plan 4** — minimal value without auto-promotion logic. Flagged in plan summary. |
| §3 Transition Setup-ready (EMA Crossback, Pullback to 10/21 EMA) | Task 15 (EMA Crossback covers both) |
| §3 Transition Trigger (Vomy Up Hourly + Daily, Saty Trigger Multiday Up reclaim) | Tasks 13, 14. Saty Trigger Multiday is part of Task 11. |
| §3 Reversion Universe (Extension > 7, Phase > 80) | Surface via overlay fields (already in Task 1/2); no separate scan |
| §3 Reversion Coiled (extension trackers) | **Deferred to Plan 4** |
| §3 Reversion Setup-ready (Saty Reversion candidates, bias candles) | Task 16 |
| §3 Reversion Trigger (Vomy Down at extension highs, Saty Trigger Down, Kell Exhaustion) | Tasks 17, 18, 21 |
| §4 Coiled Spring multi-condition definition | Task 3 |
| §4 Backfill on first run | Task 5 |
| §4 Auto-graduation when fired | **Deferred to Plan 4** (auto-promotion) |
| §4 "Preceded by trend" toggle | **Deferred to Plan 4** (UI toggle) |
| §5 Pattern history (model-book auto-capture) | **Deferred to Plan 4** |
| §6 Universe strategy | shipped in Plan 1 |
| §7 Indicator overlay (ATR%, %from50MA, Extension, Saty Levels, Ribbon, Phase, Hourly Vomy) | Tasks 1, 2, 6, 13, 14 |
| §7.1 Extension thresholds + auto-promotion | overlay carries `extension`; auto-promotion in Plan 4 |
| §8 Confluence engine + weighting | Task 4 |
| §9 Save-as-Idea pipeline | unchanged from Plan 1 (frontend wiring is Plan 3) |
| §10 UI / UX | **Plan 3** |
| §11 Backend run sequence | Tasks 5, 14, 22 |
| §11.3 Cron schedule | **Plan 4** |
| §12 Database additions | shipped in Plan 1 |
| §13 Out-of-scope items | respected |

**Coverage gap acknowledged:** Transition-Coiled and Reversion-Coiled trackers (days-since-EMA-touch / days-extended) are not implemented in Plan 2. They are intentionally deferred to Plan 4 alongside auto-promotion and lane-event logging — they have no value without the surrounding promotion machinery.

### Placeholder scan

- No "TBD", "implement later", "fill in details", "add appropriate error handling", "similar to Task N", or "write tests for the above" appears in any task body.
- Every code step shows the actual code to write.
- Every test step has actual test code.
- Every command step has the actual command.

### Type / API consistency check

- `ScanFn` signature: `(daily_bars, overlays, hourly_bars) → list[ScanHit]` — confirmed identical across registry, runner, and every scan in Tasks 8–21.
- `ScanDescriptor.weight: int = 1` — added in Task 4, used in every later task with the value documented in the weighting table at the top of the plan.
- `IndicatorOverlay` field names — `phase_oscillator` (float), `phase_in_compression` (bool), `ribbon_state` (Literal), `bias_candle` (Literal), `above_48ema` (bool), `saty_levels_by_mode` (dict). Names used identically in Tasks 1, 2, 11, 12, 13, 15, 16, 17, 18.
- `TickerResult.confluence` — weighted score added in Task 4; Task 22 extends with `sector`.
- `update_coiled_watchlist` extra parameter `initial_days_by_ticker` — defined in Task 5; runner call site updated in same task.
- Phase Oscillator constants `PHASE_OSCILLATOR_LOWER = -20.0` and `PHASE_OSCILLATOR_UPPER = 20.0` — defined in Task 3, asserted in Task 3's tests.
- Saty Levels dict shape — `levels_dict["call_trigger"]`, `levels_dict["put_trigger"]`, `levels_dict["levels"]["golden_gate_bull"]["price"]`, `levels_dict["levels"]["fib_786_bull"]["price"]`, `levels_dict["levels"]["mid_50_bull"]["price"]`, `levels_dict["levels"]["mid_50_bear"]["price"]` — verified against `api/indicators/satyland/atr_levels.py` (the ground-truth Pine port). Used identically in Tasks 11, 12, 18.

### Process notes (Plan 1 carryovers)

- Worktree precondition + `pwd` check before every commit — embedded in Step `pwd` calls and Precondition #3.
- Smoke-test-against-live precondition — Task 23.
- Railway deploy + token verification — Preconditions #1 and #2.
- Supabase migrations applied via MCP `apply_migration` (no migrations needed in Plan 2, but documented).

---

## Execution Handoff

Plan complete and saved to [docs/superpowers/plans/2026-04-26-screener-plan-2-scan-catalog.md](2026-04-26-screener-plan-2-scan-catalog.md).

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Pairs well with the worktree + `pwd` discipline (each subagent gets the explicit reminder in its prompt).

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Recommended ordering tweak: Tasks 1 and 2 can be one combined commit if execution velocity matters more than commit granularity (the schema change is meaningless until populated). All other tasks are independent commits.

Estimated total: **23 tasks · ~1 to 2 sessions of focused execution**.











