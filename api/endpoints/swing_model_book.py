from __future__ import annotations

import functools
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from supabase import Client, create_client

from api.endpoints.swing_auth import require_swing_token
from api.schemas.swing import ModelBookCreateRequest, ModelBookPatchRequest, ModelBookResponse

router = APIRouter(prefix="/api/swing/model-book", tags=["swing-model-book"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.get("", response_model=list[ModelBookResponse])
def list_entries(
    setup_kell: Optional[str] = None,
    outcome: Optional[str] = None,
    ticker: Optional[str] = None,
) -> list[ModelBookResponse]:
    sb = _get_supabase()
    q = sb.table("swing_model_book").select("*")
    if setup_kell:
        q = q.eq("setup_kell", setup_kell)
    if outcome:
        q = q.eq("outcome", outcome)
    if ticker:
        q = q.eq("ticker", ticker.upper())
    rows = q.order("created_at", desc=True).execute().data or []
    return [ModelBookResponse(**r) for r in rows]


@router.get("/{entry_id}", response_model=ModelBookResponse)
def get_entry(entry_id: UUID) -> ModelBookResponse:
    sb = _get_supabase()
    rows = sb.table("swing_model_book").select("*").eq("id", str(entry_id)).execute().data or []
    if not rows:
        raise HTTPException(404)
    return ModelBookResponse(**rows[0])


@router.post("", response_model=ModelBookResponse, status_code=201)
def create_entry(
    req: ModelBookCreateRequest, _token: None = Depends(require_swing_token),
) -> ModelBookResponse:
    sb = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid4()),
        **req.model_dump(mode="json"),
        "created_at": now,
        "updated_at": now,
    }
    sb.table("swing_model_book").insert(row).execute()

    if req.source_idea_id:
        sb.table("swing_events").insert({
            "idea_id": str(req.source_idea_id),
            "event_type": "promoted_to_model_book",
            "occurred_at": now,
            "summary": f"Added to Model Book: {req.title}",
            "payload": {"model_book_id": row["id"]},
        }).execute()

    return ModelBookResponse(**row)


@router.patch("/{entry_id}", response_model=ModelBookResponse)
def patch_entry(
    entry_id: UUID, req: ModelBookPatchRequest, _token: None = Depends(require_swing_token),
) -> ModelBookResponse:
    sb = _get_supabase()
    existing = sb.table("swing_model_book").select("*").eq("id", str(entry_id)).execute().data or []
    if not existing:
        raise HTTPException(404)
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    sb.table("swing_model_book").update(patch).eq("id", str(entry_id)).execute()
    # FakeSupabaseClient's .update().data isn't a reliable source of the updated row;
    # re-SELECT for authoritative data. Real supabase-py also varies by version.
    rows = sb.table("swing_model_book").select("*").eq("id", str(entry_id)).execute().data or []
    return ModelBookResponse(**rows[0])


@router.delete("/{entry_id}", status_code=204, response_class=Response, response_model=None)
def delete_entry(entry_id: UUID, _token: None = Depends(require_swing_token)) -> None:
    sb = _get_supabase()
    sb.table("swing_model_book").delete().eq("id", str(entry_id)).execute()
