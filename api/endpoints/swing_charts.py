"""Swing chart endpoints — record chart URLs, list by idea/event/model-book.

The actual image bytes live in Vercel Blob. The Next.js client uploads there
directly, then POSTs the resulting URL here.
"""
from __future__ import annotations

import functools
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client, create_client

from api.endpoints.swing_auth import require_swing_token
from api.schemas.swing import ChartCreateRequest, ChartResponse

router = APIRouter(tags=["swing-charts"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.post("/api/swing/charts", response_model=ChartResponse, status_code=201)
def create_chart(req: ChartCreateRequest, _token: None = Depends(require_swing_token)) -> ChartResponse:
    owners = [req.idea_id, req.event_id, req.model_book_id]
    if sum(1 for o in owners if o is not None) != 1:
        raise HTTPException(400, "Exactly one of idea_id, event_id, model_book_id must be set")
    sb = _get_supabase()
    row = {
        "id": str(uuid4()),
        "idea_id": str(req.idea_id) if req.idea_id else None,
        "event_id": req.event_id,
        "model_book_id": str(req.model_book_id) if req.model_book_id else None,
        "image_url": req.image_url,
        "thumbnail_url": req.thumbnail_url,
        "timeframe": req.timeframe,
        "source": req.source,
        "annotations": req.annotations,
        "caption": req.caption,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    sb.table("swing_charts").insert(row).execute()

    # Append a chart_uploaded event on the idea (if attached to an idea)
    if req.idea_id:
        sb.table("swing_events").insert({
            "idea_id": str(req.idea_id),
            "event_type": "chart_uploaded",
            "occurred_at": row["captured_at"],
            "summary": f"Chart uploaded ({req.timeframe}, {req.source})",
            "payload": {"chart_id": row["id"], "image_url": req.image_url},
        }).execute()

    return ChartResponse(**row)


@router.get("/api/swing/ideas/{idea_id}/charts", response_model=list[ChartResponse])
def list_idea_charts(idea_id: UUID) -> list[ChartResponse]:
    sb = _get_supabase()
    rows = sb.table("swing_charts").select("*").eq("idea_id", str(idea_id)).order("captured_at", desc=True).execute().data or []
    return [ChartResponse(**r) for r in rows]


@router.get("/api/swing/events/{event_id}/charts", response_model=list[ChartResponse])
def list_event_charts(event_id: int) -> list[ChartResponse]:
    sb = _get_supabase()
    rows = sb.table("swing_charts").select("*").eq("event_id", event_id).execute().data or []
    return [ChartResponse(**r) for r in rows]


@router.get("/api/swing/model-book/{model_book_id}/charts", response_model=list[ChartResponse])
def list_model_book_charts(model_book_id: UUID) -> list[ChartResponse]:
    sb = _get_supabase()
    rows = sb.table("swing_charts").select("*").eq("model_book_id", str(model_book_id)).execute().data or []
    return [ChartResponse(**r) for r in rows]
