"""Snapshots endpoint.

GET list by idea_id (open — consumed by frontend proxy)
POST upsert by natural key (idea_id, snapshot_date, snapshot_type).
Used both by Mac-Claude (to attach claude_analysis + chart URLs) and,
in emergencies, to hand-patch a snapshot.
"""
from __future__ import annotations

import functools
import os
from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client, create_client

from api.endpoints.swing_auth import require_swing_token
from api.schemas.swing import SnapshotCreateRequest, SnapshotResponse

router = APIRouter(tags=["swing-snapshots"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.get("/api/swing/ideas/{idea_id}/snapshots", response_model=list[SnapshotResponse])
def list_snapshots(idea_id: UUID) -> list[SnapshotResponse]:
    sb = _get_supabase()
    rows = (sb.table("swing_idea_snapshots").select("*")
            .eq("idea_id", str(idea_id)).order("snapshot_date", desc=True)
            .execute().data or [])
    return [SnapshotResponse(**r) for r in rows]


@router.post("/api/swing/ideas/{idea_id}/snapshots", response_model=SnapshotResponse)
def upsert_snapshot(
    idea_id: UUID, req: SnapshotCreateRequest, _token: None = Depends(require_swing_token),
) -> SnapshotResponse:
    sb = _get_supabase()
    existing = (sb.table("swing_idea_snapshots").select("*")
                .eq("idea_id", str(idea_id))
                .eq("snapshot_date", req.snapshot_date.isoformat())
                .eq("snapshot_type", req.snapshot_type).execute().data or [])
    patch = {k: v for k, v in req.model_dump().items() if v is not None and k not in ("snapshot_date", "snapshot_type")}
    if existing:
        row = existing[0]
        row.update(patch)
        sb.table("swing_idea_snapshots").update(patch).eq("id", row["id"]).execute()
        return SnapshotResponse(**row)
    row = {
        "idea_id": str(idea_id),
        "snapshot_date": req.snapshot_date.isoformat(),
        "snapshot_type": req.snapshot_type,
        **patch,
    }
    inserted = sb.table("swing_idea_snapshots").insert(row).execute()
    return SnapshotResponse(**(inserted.data[0] if hasattr(inserted, "data") else row))
