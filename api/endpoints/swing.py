"""Swing trading endpoints — universe management in this plan; detection/analysis in later plans."""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Header
from supabase import Client, create_client

from api.indicators.swing.universe.resolver import (
    resolve_universe,
    save_universe_batch,
)
from api.endpoints.swing_auth import require_swing_token, idempotent
from api.endpoints import swing_ticker_service as svc
from api.schemas.swing import (
    EventWriteRequest,
    EventWriteResponse,
    PipelineRunResponse,
    SwingIdea,
    SwingIdeaListResponse,
    ThesisWriteRequest,
    ThesisWriteResponse,
    TickerBarEntry,
    TickerBarsResponse,
    TickerDetectResponse,
    TickerFundamentalsResponse,
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
def list_ideas(
    status: str | None = None,
    thesis_status: str | None = None,
    ticker: str | None = None,
    limit: int = 50,
):
    sb = _get_supabase()
    q = sb.table("swing_ideas").select("*")
    if status:
        q = q.eq("status", status)
    if thesis_status:
        q = q.eq("thesis_status", thesis_status)
    if ticker:
        q = q.eq("ticker", ticker.upper())
    # Chained .order() — primary: confluence_score desc, secondary: detected_at desc.
    # Both FakeSupabaseClient and real supabase-py apply orders in the order given.
    rows = (
        q.order("confluence_score", desc=True)
        .order("detected_at", desc=True)
        .limit(limit)
        .execute()
        .data or []
    )
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


def _verify_cron_auth(authorization: str | None) -> None:
    """Verify Bearer token against CRON_SECRET.

    When the env var is unset (None) we skip — this is intentional for local dev.
    An EMPTY-string CRON_SECRET is treated as misconfiguration and we still skip,
    but we log a warning so it's visible. Production deploys must set a real value.
    """
    import logging
    secret = os.environ.get("CRON_SECRET")
    if secret is None:
        return
    if secret == "":
        logging.getLogger(__name__).warning(
            "CRON_SECRET is empty — cron endpoint is unprotected. "
            "Set CRON_SECRET to a non-empty value in production."
        )
        return
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/pipeline/premarket", response_model=PipelineRunResponse)
def run_premarket(authorization: str | None = Header(default=None)):
    _verify_cron_auth(authorization)
    from api.indicators.swing.pipeline import run_premarket_detection
    sb = _get_supabase()
    result = run_premarket_detection(sb)
    return PipelineRunResponse(**result)


@router.post("/ideas/{idea_id}/thesis", response_model=ThesisWriteResponse,
             dependencies=[Depends(require_swing_token)])
def write_thesis(
    idea_id: UUID,
    req: ThesisWriteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    sb = _get_supabase()
    idea = sb.table("swing_ideas").select("id").eq("id", str(idea_id)).execute().data or []
    if not idea:
        raise HTTPException(status_code=404, detail=f"idea {idea_id} not found")

    def _do() -> dict:
        now = datetime.now(timezone.utc).isoformat()
        patch: dict = {}
        if req.layer == "base":
            patch = {
                "base_thesis": req.text,
                "base_thesis_at": now,
                "thesis_status": "ready",
            }
        else:  # deep
            patch = {
                "deep_thesis": req.text,
                "deep_thesis_at": now,
                "deep_thesis_sources": req.sources,
            }
        sb.table("swing_ideas").update(patch).eq("id", str(idea_id)).execute()
        sb.table("swing_events").insert({
            "idea_id": str(idea_id),
            "event_type": "thesis_updated",
            "occurred_at": now,
            "payload": {"layer": req.layer, "model": req.model},
            "summary": f"{req.layer} thesis updated",
        }).execute()
        return {"idea_id": str(idea_id), "layer": req.layer, "updated_at": now}

    return idempotent(sb, idempotency_key, f"/ideas/{idea_id}/thesis", _do)


@router.post("/ideas/{idea_id}/events", response_model=EventWriteResponse,
             dependencies=[Depends(require_swing_token)])
def write_event(
    idea_id: UUID,
    req: EventWriteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    sb = _get_supabase()
    if not sb.table("swing_ideas").select("id").eq("id", str(idea_id)).execute().data:
        raise HTTPException(status_code=404, detail=f"idea {idea_id} not found")

    def _do() -> dict:
        now = datetime.now(timezone.utc).isoformat()
        ret = sb.table("swing_events").insert({
            "idea_id": str(idea_id),
            "event_type": req.event_type,
            "occurred_at": now,
            "payload": req.payload,
            "summary": req.summary,
        }).execute()
        row = (ret.data or [{}])[0] if hasattr(ret, "data") else {}
        return {
            "event_id": row.get("id", 0),
            "idea_id": str(idea_id),
            "occurred_at": now,
        }

    return idempotent(sb, idempotency_key, f"/ideas/{idea_id}/events", _do)


@router.get("/ticker/{ticker}/bars", response_model=TickerBarsResponse)
def get_ticker_bars(
    ticker: str,
    tf: str = Query(..., pattern="^(daily|weekly|60m)$"),
    lookback: int = Query(90, ge=5, le=1000),
):
    df = svc.fetch_bars(ticker.upper(), tf, lookback)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No bars for {ticker}")
    return TickerBarsResponse(
        ticker=ticker.upper(),
        tf=tf,
        bars=[TickerBarEntry(**r) for r in df.to_dict(orient="records")],
    )


@router.get("/ticker/{ticker}/fundamentals", response_model=TickerFundamentalsResponse)
def get_ticker_fundamentals(ticker: str):
    data = svc.fetch_fundamentals(ticker.upper())
    return TickerFundamentalsResponse(ticker=ticker.upper(), **data)


import dataclasses


class InsufficientData(Exception):
    """Raised when a ticker has < 60 bars of history — not enough for Kell detectors."""


def _run_detectors_for_ticker(ticker: str) -> list[dict]:
    """Run all 5 Plan 2 detectors against a single ticker's daily bars.

    Plan 2 exposes detectors individually, not as a single `run_all_detectors_for_ticker`
    helper, so we compose them here.
    """
    from api.indicators.swing.setups.wedge_pop import detect as detect_wedge_pop
    from api.indicators.swing.setups.ema_crossback import detect as detect_ema_crossback
    from api.indicators.swing.setups.base_n_break import detect as detect_base_n_break
    from api.indicators.swing.setups.reversal_extension import detect as detect_reversal_extension
    from api.indicators.swing.setups.post_eps_flag import detect as detect_post_eps_flag

    daily = svc.fetch_bars(ticker, "daily", lookback=250)
    if len(daily) < 60:
        raise InsufficientData(f"only {len(daily)} daily bars")
    qqq = svc.fetch_bars("QQQ", "daily", lookback=250)
    ctx = {"ticker": ticker, "universe_extras": {}, "prior_ideas": [],
           "today": datetime.now(timezone.utc).date(), "rs_10d": 0.0, "theme_leaders": []}

    detectors = [
        detect_wedge_pop, detect_ema_crossback, detect_base_n_break,
        detect_reversal_extension, detect_post_eps_flag,
    ]
    hits: list = []
    for d in detectors:
        try:
            hit = d(daily, qqq, ctx)
            if hit is not None:
                hits.append(hit)
        except Exception:
            # Per-detector failures are swallowed — the detect endpoint is best-effort.
            pass

    return [dataclasses.asdict(h) if dataclasses.is_dataclass(h) else dict(h) for h in hits]


def _ticker_health_snapshot() -> dict:
    """QQQ-based market health (Plan 2 snapshot dict)."""
    from api.indicators.swing.market_health import compute_market_health
    qqq = svc.fetch_bars("QQQ", "daily", lookback=60)
    if qqq.empty or len(qqq) < 20:
        return {}
    mh = compute_market_health(qqq)
    return mh.snapshot


@router.post("/ticker/{ticker}/detect", response_model=TickerDetectResponse,
             dependencies=[Depends(require_swing_token)])
def detect_for_ticker(ticker: str):
    ticker = ticker.upper()
    try:
        setups = _run_detectors_for_ticker(ticker)
    except InsufficientData as e:
        fund = svc.fetch_fundamentals(ticker)
        return TickerDetectResponse(
            ticker=ticker, setups=[], fundamentals=fund.get("fundamentals") or {},
            market_health={}, data_sufficient=False, reason=str(e),
        )
    fund = svc.fetch_fundamentals(ticker)
    return TickerDetectResponse(
        ticker=ticker,
        setups=setups,
        fundamentals=fund.get("fundamentals") or {},
        market_health=_ticker_health_snapshot(),
        data_sufficient=True,
    )
