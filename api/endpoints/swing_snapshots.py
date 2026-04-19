"""Snapshots endpoint.

GET list by idea_id (open — consumed by frontend proxy)
POST upsert by natural key (idea_id, snapshot_date, snapshot_type).
Used both by Mac-Claude (to attach claude_analysis + chart URLs) and,
in emergencies, to hand-patch a snapshot.
"""
from __future__ import annotations

import functools
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client, create_client

from api.endpoints.swing_auth import require_swing_token
from api.schemas.swing import SnapshotCreateRequest, SnapshotResponse

logger = logging.getLogger(__name__)
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
    try:
        sb.table("swing_idea_snapshots").insert(row).execute()
    except Exception as exc:
        # UNIQUE(idea_id, snapshot_date, snapshot_type) race with the pipeline:
        # fall through to UPDATE on the existing row.
        logger.warning(
            "Snapshot insert raced (idea_id=%s, date=%s); retrying as update: %s",
            idea_id, req.snapshot_date.isoformat(), exc,
        )
        sb.table("swing_idea_snapshots").update(patch).eq("idea_id", str(idea_id)).eq(
            "snapshot_date", req.snapshot_date.isoformat()
        ).eq("snapshot_type", req.snapshot_type).execute()
    # Re-SELECT so we return the authoritative DB row (including server-assigned `id`).
    fresh = (sb.table("swing_idea_snapshots").select("*")
             .eq("idea_id", str(idea_id))
             .eq("snapshot_date", req.snapshot_date.isoformat())
             .eq("snapshot_type", req.snapshot_type).execute().data or [])
    if not fresh:
        raise HTTPException(500, "Snapshot write succeeded but re-SELECT returned nothing")
    return SnapshotResponse(**fresh[0])
