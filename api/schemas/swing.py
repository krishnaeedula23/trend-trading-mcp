from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UniverseTicker(BaseModel):
    ticker: str
    source: Literal["deepvue-csv", "manual", "backend-generated"]
    batch_id: UUID
    added_at: datetime
    extras: dict[str, Any] | None = None


class UniverseListResponse(BaseModel):
    tickers: list[UniverseTicker]
    source_summary: dict[str, int]   # {"deepvue-csv": 152, "manual": 3}
    active_count: int
    latest_batch_at: datetime | None


class UniverseAddSingleRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)

    @field_validator("ticker")
    @classmethod
    def uppercase_and_strip(cls, v: str) -> str:
        return v.strip().upper()


class UniverseUploadResponse(BaseModel):
    batch_id: UUID
    mode: Literal["replace", "add"]
    tickers_added: int
    tickers_removed: int
    total_active: int


class UniverseHistoryEntry(BaseModel):
    batch_id: UUID
    source: str
    uploaded_at: datetime
    ticker_count: int


class UniverseHistoryResponse(BaseModel):
    batches: list[UniverseHistoryEntry]


class SwingIdea(BaseModel):
    id: UUID
    ticker: str
    cycle_stage: str
    setup_kell: str
    confluence_score: int
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop_price: float
    first_target: float | None = None
    second_target: float | None = None
    status: str                           # 'active' | 'watching' | 'exited' | 'invalidated'
    detected_at: datetime
    base_thesis: str | None = None
    thesis_status: str                    # 'pending' | 'ready'
    market_health: dict[str, Any] | None = None
    risk_flags: dict[str, Any]
    detection_evidence: dict[str, Any] | None = None


class SwingIdeaListResponse(BaseModel):
    ideas: list[SwingIdea]
    total: int


class PipelineRunResponse(BaseModel):
    new_ideas: int
    transitions: int
    invalidations: int
    errors: int = 0
    universe_source: str
    universe_size: int
    market_health: dict[str, Any] = {}


# ── Plan 3: Claude-analysis-layer endpoints ─────────────────────────────────

class ThesisWriteRequest(BaseModel):
    layer: Literal["base", "deep"]
    text: str = Field(min_length=10, max_length=20_000)
    model: str                            # e.g. "claude-opus-4-7"
    sources: list[str] | None = None      # URLs/filenames referenced
    deepvue_panel: dict | None = None     # deep-layer only; base can pass None


class ThesisWriteResponse(BaseModel):
    idea_id: str
    layer: Literal["base", "deep"]
    updated_at: str


class EventWriteRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    payload: dict | None = None
    summary: str | None = Field(default=None, max_length=2_000)


class EventWriteResponse(BaseModel):
    event_id: int
    idea_id: str
    occurred_at: str


class TickerBarEntry(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class TickerBarsResponse(BaseModel):
    ticker: str
    tf: Literal["daily", "weekly", "60m"]
    bars: list[TickerBarEntry]


class TickerFundamentalsResponse(BaseModel):
    ticker: str
    fundamentals: dict
    next_earnings_date: date | None = None
    beta: float | None = None
    avg_daily_dollar_volume: float | None = None


class TickerDetectResponse(BaseModel):
    ticker: str
    # Each setup is a serialized SetupHit dict PLUS `confluence_score: int` composed
    # by api.indicators.swing.confluence.score_hits (so ad-hoc /detect output is
    # comparable with pipeline-scored swing_ideas rows).
    setups: list[dict]
    fundamentals: dict
    next_earnings_date: date | None = None
    beta: float | None = None
    avg_daily_dollar_volume: float | None = None
    market_health: dict
    data_sufficient: bool        # false if yfinance returned <60 bars
    reason: str | None = None    # populated when data_sufficient=false


class SnapshotCreateRequest(BaseModel):
    snapshot_date: date
    snapshot_type: Literal["daily", "weekly"] = "daily"
    # Railway-populated (optional on Mac-side POST; required on Railway-internal upsert)
    daily_close: float | None = None
    daily_high: float | None = None
    daily_low: float | None = None
    daily_volume: int | None = None
    ema_10: float | None = None
    ema_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    weekly_ema_10: float | None = None
    rs_vs_qqq_20d: float | None = None
    phase_osc_value: float | None = None
    kell_stage: str | None = None
    saty_setups_active: list[str] | None = None
    # Mac-populated
    claude_analysis: str | None = None
    claude_model: str | None = None
    analysis_sources: dict[str, Any] | None = None
    deepvue_panel: dict[str, Any] | None = None
    chart_daily_url: str | None = None
    chart_weekly_url: str | None = None
    chart_60m_url: str | None = None


class SnapshotResponse(SnapshotCreateRequest):
    id: int
    idea_id: UUID


class EventCreateRequest(BaseModel):
    event_type: Literal[
        "stage_transition", "thesis_updated", "setup_fired", "invalidation",
        "earnings", "exhaustion_warning", "user_note", "chart_uploaded",
        "trade_recorded", "promoted_to_model_book",
    ]
    payload: dict[str, Any] | None = None
    summary: str | None = None


class EventResponse(BaseModel):
    id: int
    idea_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any] | None
    summary: str | None


class ChartCreateRequest(BaseModel):
    image_url: str
    thumbnail_url: str | None = None
    timeframe: Literal["daily", "weekly", "60m", "annotated"]
    source: Literal["deepvue-auto", "tradingview-upload", "user-markup", "claude-annotated"]
    annotations: dict[str, Any] | None = None
    caption: str | None = None
    # Exactly one must be set (enforced server-side and by DB CHECK):
    idea_id: UUID | None = None
    event_id: int | None = None
    model_book_id: UUID | None = None


class ChartResponse(ChartCreateRequest):
    id: UUID
    captured_at: datetime


class ModelBookCreateRequest(BaseModel):
    title: str
    ticker: str
    setup_kell: str
    outcome: Literal["winner", "loser", "example", "missed"]
    entry_date: date | None = None
    exit_date: date | None = None
    r_multiple: float | None = None
    source_idea_id: UUID | None = None
    ticker_fundamentals: dict[str, Any] | None = None
    narrative: str | None = None
    key_takeaways: list[str] | None = None
    tags: list[str] | None = None


class ModelBookPatchRequest(BaseModel):
    narrative: str | None = None
    key_takeaways: list[str] | None = None
    tags: list[str] | None = None
    outcome: Literal["winner", "loser", "example", "missed"] | None = None


class ModelBookResponse(ModelBookCreateRequest):
    id: UUID
    created_at: datetime
    updated_at: datetime


class PostmarketRunResponse(BaseModel):
    ran_at: datetime
    active_ideas_processed: int
    stage_transitions: int
    exhaustion_warnings: int
    stop_violations: int
    snapshots_written: int


class UniverseRefreshResponse(BaseModel):
    ran_at: datetime
    skipped: bool
    skip_reason: str | None = None
    base_count: int | None = None
    final_count: int | None = None
    batch_id: UUID | None = None


class WeeklyEntry(BaseModel):
    idea_id: str
    ticker: str
    cycle_stage: str | None
    status: str
    claude_analysis: str | None


class WeekGroup(BaseModel):
    week_of: str
    entries: list[WeeklyEntry]
