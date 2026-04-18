from datetime import datetime
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
    thesis_status: str                    # 'pending' | 'generated' | 'refined'
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
    universe_source: str
    universe_size: int
    market_health: dict[str, Any] = {}


class SetupHitResponse(BaseModel):
    """Compact detector output for ad-hoc detection — used in Plan 3."""
    ticker: str
    setup_kell: str
    cycle_stage: str
    entry_zone: tuple[float, float]
    stop_price: float
    first_target: float | None = None
    second_target: float | None = None
    detection_evidence: dict[str, Any]
    raw_score: int
