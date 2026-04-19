from __future__ import annotations

import functools
import os
from collections import defaultdict

from fastapi import APIRouter
from pydantic import BaseModel
from supabase import Client, create_client

router = APIRouter(tags=["swing-weekly"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


class WeeklyEntry(BaseModel):
    idea_id: str
    ticker: str
    cycle_stage: str | None
    status: str
    claude_analysis: str | None


class WeekGroup(BaseModel):
    week_of: str
    entries: list[WeeklyEntry]


@router.get("/api/swing/weekly", response_model=list[WeekGroup])
def list_weekly() -> list[WeekGroup]:
    sb = _get_supabase()
    snaps = (sb.table("swing_idea_snapshots").select("*")
             .eq("snapshot_type", "weekly").order("snapshot_date", desc=True)
             .execute().data or [])
    ideas = {i["id"]: i for i in (sb.table("swing_ideas").select("*").execute().data or [])}

    grouped: dict[str, list[WeeklyEntry]] = defaultdict(list)
    for s in snaps:
        idea = ideas.get(s["idea_id"])
        if not idea:
            continue
        grouped[s["snapshot_date"]].append(WeeklyEntry(
            idea_id=s["idea_id"],
            ticker=idea["ticker"],
            cycle_stage=idea.get("cycle_stage"),
            status=idea["status"],
            claude_analysis=s.get("claude_analysis"),
        ))

    return [WeekGroup(week_of=w, entries=grouped[w]) for w in sorted(grouped.keys(), reverse=True)]
