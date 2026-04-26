"""Pydantic schemas for the unified morning screener API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Mode = Literal["swing", "position"]
Lane = Literal["breakout", "transition", "reversion"]
Role = Literal["universe", "coiled", "setup_ready", "trigger"]


class IndicatorOverlay(BaseModel):
    """Per-ticker indicator stack computed once per run."""
    atr_pct: float = Field(..., description="ATR(14) / close")
    pct_from_50ma: float = Field(..., description="(close - SMA50) / SMA50")
    extension: float = Field(..., description="jfsrev formula: B/A")
    sma_50: float
    atr_14: float


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
    confluence: int


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
