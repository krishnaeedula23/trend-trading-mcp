"""Swing trading endpoints — universe management in this plan; detection/analysis in later plans."""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from supabase import Client, create_client

from api.indicators.swing.universe.resolver import (
    resolve_universe,
    save_universe_batch,
)
from api.schemas.swing import (
    SwingIdea,
    SwingIdeaListResponse,
    UniverseAddSingleRequest,
    UniverseHistoryEntry,
    UniverseHistoryResponse,
    UniverseListResponse,
    UniverseTicker,
    UniverseUploadResponse,
)

router = APIRouter(prefix="/api/swing", tags=["swing"])

_supabase: Client | None = None


def _get_supabase() -> Client:
    """Module-level singleton — matches market_monitor.py pattern.
    Tests monkey-patch this function."""
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _supabase = create_client(url, key)
    return _supabase


@router.get("/universe", response_model=UniverseListResponse)
def get_universe():
    sb = _get_supabase()
    resolved = resolve_universe(sb)
    all_active = (
        sb.table("swing_universe").select("*").is_("removed_at", None).order("added_at", desc=True).execute().data
        or []
    )
    source_summary: dict[str, int] = {}
    for r in all_active:
        source_summary[r["source"]] = source_summary.get(r["source"], 0) + 1
    return UniverseListResponse(
        tickers=[
            UniverseTicker(
                ticker=r["ticker"],
                source=r["source"],
                batch_id=r["batch_id"],
                added_at=r["added_at"],
                extras=r.get("extras"),
            )
            for r in all_active
        ],
        source_summary=source_summary,
        active_count=len(all_active),
        latest_batch_at=resolved.latest_upload,
    )


@router.post("/universe", response_model=UniverseTicker)
def add_single_ticker(req: UniverseAddSingleRequest):
    sb = _get_supabase()
    existing = (
        sb.table("swing_universe")
        .select("*")
        .eq("ticker", req.ticker)
        .is_("removed_at", None)
        .execute()
        .data
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{req.ticker} already in active universe")

    batch_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "ticker": req.ticker,
        "source": "manual",
        "batch_id": str(batch_id),
        "added_at": now,
        "removed_at": None,
        "extras": {},
    }
    sb.table("swing_universe").insert(row).execute()
    return UniverseTicker(**row)


@router.post("/universe/upload", response_model=UniverseUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    mode: str = Form(...),
):
    sb = _get_supabase()
    if mode not in ("replace", "add"):
        raise HTTPException(status_code=400, detail="mode must be 'replace' or 'add'")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Expected .csv file")

    body = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(body))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    ticker_col = next((c for c in reader.fieldnames if c.lower() in ("ticker", "symbol")), None)
    if ticker_col is None:
        raise HTTPException(status_code=400, detail="CSV must contain a 'ticker' or 'symbol' column")

    tickers_with_extras: dict[str, dict] = {}
    for row in reader:
        t = (row.get(ticker_col) or "").strip().upper()
        if not t:
            continue
        extras = {k: v for k, v in row.items() if k != ticker_col and v not in ("", None)}
        tickers_with_extras[t] = extras
    if not tickers_with_extras:
        raise HTTPException(status_code=400, detail="CSV had no usable tickers")

    removed_before = 0
    if mode == "replace":
        existing = (
            sb.table("swing_universe").select("id").eq("source", "deepvue-csv").is_("removed_at", None).execute().data or []
        )
        removed_before = len(existing)

    batch_id = save_universe_batch(sb, tickers_with_extras, source="deepvue-csv", mode=mode)
    active_count = len(sb.table("swing_universe").select("id").is_("removed_at", None).execute().data or [])

    return UniverseUploadResponse(
        batch_id=batch_id,
        mode=mode,
        tickers_added=len(tickers_with_extras),
        tickers_removed=removed_before,
        total_active=active_count,
    )


@router.get("/ideas", response_model=SwingIdeaListResponse)
def list_ideas(status: str | None = None, limit: int = 50):
    sb = _get_supabase()
    q = sb.table("swing_ideas").select("*")
    if status:
        q = q.eq("status", status)
    # Order by confluence desc, detected_at desc — FakeSupabaseClient supports .order(col, desc)
    rows = q.order("confluence_score", desc=True).limit(limit).execute().data or []
    # Secondary sort by detected_at in Python (fake client only supports one .order())
    rows.sort(key=lambda r: (r.get("confluence_score", 0), r.get("detected_at") or ""), reverse=True)
    ideas = [SwingIdea(**r) for r in rows]
    return SwingIdeaListResponse(ideas=ideas, total=len(ideas))


@router.get("/ideas/{idea_id}", response_model=SwingIdea)
def get_idea(idea_id: UUID):
    sb = _get_supabase()
    rows = sb.table("swing_ideas").select("*").eq("id", str(idea_id)).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return SwingIdea(**rows[0])


@router.delete("/universe/{ticker}")
def remove_ticker(ticker: str):
    sb = _get_supabase()
    ticker = ticker.upper()
    existing = (
        sb.table("swing_universe").select("*").eq("ticker", ticker).is_("removed_at", None).execute().data or []
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"{ticker} not in active universe")
    now = datetime.now(timezone.utc).isoformat()
    sb.table("swing_universe").update({"removed_at": now}).eq("ticker", ticker).is_("removed_at", None).execute()
    return {"removed": ticker, "removed_at": now}


@router.get("/universe/history", response_model=UniverseHistoryResponse)
def get_universe_history():
    sb = _get_supabase()
    rows = sb.table("swing_universe").select("batch_id, source, added_at").order("added_at", desc=True).execute().data or []
    batches: dict[str, UniverseHistoryEntry] = {}
    for r in rows:
        bid = r["batch_id"]
        if bid not in batches:
            batches[bid] = UniverseHistoryEntry(batch_id=bid, source=r["source"], uploaded_at=r["added_at"], ticker_count=1)
        else:
            batches[bid].ticker_count += 1
    return UniverseHistoryResponse(batches=list(batches.values())[:50])
