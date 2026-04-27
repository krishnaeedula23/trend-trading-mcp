"""Morning screener endpoints — run scans, manage universe overrides.

Routes:
  POST /api/screener/morning/run         — run all scans for a mode, return results
  GET  /api/screener/universe             — show base + overrides + effective list
  POST /api/screener/universe/update      — add/remove/replace/clear overrides
"""
from __future__ import annotations

import logging
import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client, create_client

from api.endpoints.swing_auth import require_swing_token
from api.indicators.screener.bars import fetch_daily_bars_bulk, fetch_hourly_bars_bulk
from api.indicators.screener.runner import run_screener
from api.indicators.screener.universe_override import (
    add_overrides,
    apply_overrides,
    clear_overrides,
    list_overrides,
    remove_overrides,
)
# Reuses the swing universe resolver as the base universe source.
from api.indicators.swing.universe.resolver import resolve_universe
from api.schemas.screener import (
    Mode,
    ScreenerRunRequest,
    ScreenerRunResponse,
    UniverseShowResponse,
    UniverseUpdateRequest,
    UniverseUpdateResponse,
)

# Side effect: registers the coiled_spring scan
import api.indicators.screener.scans  # noqa: F401


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])


def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _resolve_base_universe(sb: Client, mode: Mode) -> tuple[list[str], str]:
    """For Plan 1, swing mode reuses the existing swing universe.
    Position mode raises until Plan 4 adds it.
    """
    if mode != "swing":
        raise HTTPException(status_code=501, detail=f"mode '{mode}' not supported in Plan 1")
    resolved = resolve_universe(sb)
    return list(resolved.tickers), resolved.source


def _resolve_active_universe(sb: Client, mode: Mode) -> list[str]:
    base, _ = _resolve_base_universe(sb, mode)
    return apply_overrides(sb, base, mode)


@router.post(
    "/morning/run",
    response_model=ScreenerRunResponse,
    dependencies=[Depends(require_swing_token)],
)
def run_morning(req: ScreenerRunRequest) -> ScreenerRunResponse:
    sb = _get_supabase()
    tickers = _resolve_active_universe(sb, req.mode)
    if not tickers:
        raise HTTPException(status_code=400, detail="Active universe is empty.")
    daily = fetch_daily_bars_bulk(sorted(set(tickers) | {"QQQ"}), period="6mo")
    hourly = fetch_hourly_bars_bulk(tickers, period="60d")
    return run_screener(
        sb=sb,
        mode=req.mode,
        bars_by_ticker=daily,
        hourly_bars_by_ticker=hourly,
        today=date.today(),
        scan_ids=req.scan_ids,
    )


@router.get("/universe", response_model=UniverseShowResponse)
def get_universe(mode: Mode = "swing") -> UniverseShowResponse:
    sb = _get_supabase()
    base, source = _resolve_base_universe(sb, mode)
    added, removed = list_overrides(sb, mode)
    eff = sorted((set(base) | set(added)) - set(removed))
    return UniverseShowResponse(
        mode=mode,
        base_tickers=sorted(base),
        overrides_added=added,
        overrides_removed=removed,
        effective_tickers=eff,
        base_source=source,
    )


@router.post(
    "/universe/update",
    response_model=UniverseUpdateResponse,
    dependencies=[Depends(require_swing_token)],
)
def update_universe(req: UniverseUpdateRequest) -> UniverseUpdateResponse:
    sb = _get_supabase()

    if req.action == "add":
        add_overrides(sb, mode=req.mode, tickers=req.tickers)
    elif req.action == "remove":
        remove_overrides(sb, mode=req.mode, tickers=req.tickers)
    elif req.action == "replace":
        # Note: not atomic — clear + add are two Supabase calls. If the second
        # fails, overrides are left empty. Acceptable for v1 (low-frequency,
        # human-driven via Claude skill); revisit in Plan 2 if it bites.
        clear_overrides(sb, mode=req.mode)
        try:
            add_overrides(sb, mode=req.mode, tickers=req.tickers)
        except Exception:
            logger.exception(
                "replace action: clear succeeded but add failed for mode=%s; "
                "overrides are now empty",
                req.mode,
            )
            raise
    elif req.action == "clear_overrides":
        clear_overrides(sb, mode=req.mode)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    base, _ = _resolve_base_universe(sb, req.mode)
    added, removed = list_overrides(sb, req.mode)
    eff = (set(base) | set(added)) - set(removed)
    return UniverseUpdateResponse(
        mode=req.mode,
        overrides_added=added,
        overrides_removed=removed,
        effective_size=len(eff),
    )
