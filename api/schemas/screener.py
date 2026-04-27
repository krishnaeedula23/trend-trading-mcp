"""Pydantic schemas for the unified morning screener API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Mode = Literal["swing", "position"]
Lane = Literal["breakout", "transition", "reversion"]
Role = Literal["universe", "coiled", "setup_ready", "trigger"]
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


class ScanHit(BaseModel):
    """A single (ticker, scan_id) pairing emitted by a scan."""
    ticker: str
    scan_id: str
    lane: Lane
    role: Role
    evidence: dict = Field(
        default_factory=dict,
        description="Per-scan evidence payload; shape is owned by each scan implementation.",
    )


class ScreenerRunRequest(BaseModel):
    mode: Mode = "swing"
    scan_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of scans to run; if None, runs all registered scans for the mode.",
    )


class TickerResult(BaseModel):
    ticker: str
    last_close: float
    overlay: IndicatorOverlay
    scans_hit: list[str]
    confluence: int = Field(..., description="Weighted score: sum of scan weights for hits")
    confluence_weight: int = Field(..., description="Same value as confluence; explicit name when raw count also surfaced")


class ScreenerRunResponse(BaseModel):
    run_id: str
    mode: Mode
    ran_at: datetime
    universe_size: int
    scan_count: int = Field(
        ...,
        description="Number of scans dispatched in this run (i.e. registered scans for the mode after optional scan_ids filter). Not the number of (ticker, scan) hit pairings — see hit_count for tickers with at least one hit.",
    )
    hit_count: int
    duration_seconds: float
    tickers: list[TickerResult]


class UniverseShowResponse(BaseModel):
    mode: Mode
    base_tickers: list[str]
    overrides_added: list[str]
    overrides_removed: list[str]
    effective_tickers: list[str]
    base_source: str


class UniverseUpdateRequest(BaseModel):
    mode: Mode
    action: Literal["add", "remove", "replace", "clear_overrides"]
    tickers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _tickers_required_for_mutating_actions(self) -> "UniverseUpdateRequest":
        if self.action in ("add", "remove", "replace") and not self.tickers:
            raise ValueError(f"action '{self.action}' requires a non-empty tickers list")
        return self


class UniverseUpdateResponse(BaseModel):
    mode: Mode
    overrides_added: list[str]
    overrides_removed: list[str]
    effective_size: int


class CoiledEntry(BaseModel):
    ticker: str
    mode: Mode
    first_detected_at: date
    last_seen_at: date
    days_in_compression: int
    status: Literal["active", "fired", "broken"]
