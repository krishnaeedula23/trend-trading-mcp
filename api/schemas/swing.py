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
