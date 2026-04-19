"""Post-market Railway endpoint.

POST /api/swing/pipeline/postmarket  (CRON_SECRET-protected; called by daily-dispatcher at 21:00 UTC)

/universe-refresh will be added by Plan 4 Task 6 once the helper exists.
Uses the same _verify_cron_auth pattern as /pipeline/premarket in swing.py so the
Vercel cron's `authToken: cronSecret` bearer is accepted.
"""
from __future__ import annotations

import functools
import logging
import os

from fastapi import APIRouter, Header

from api.endpoints.swing import _verify_cron_auth
from supabase import Client, create_client

from api.indicators.swing.pipeline.postmarket import run_swing_postmarket_snapshot
from api.schemas.swing import PostmarketRunResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/swing/pipeline", tags=["swing-pipeline"])


@functools.lru_cache(maxsize=1)
def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.post("/postmarket", response_model=PostmarketRunResponse)
def trigger_postmarket(authorization: str | None = Header(default=None)) -> PostmarketRunResponse:
    _verify_cron_auth(authorization)
    sb = _get_supabase()
    result = run_swing_postmarket_snapshot(sb)
    return PostmarketRunResponse(
        ran_at=result.ran_at,
        active_ideas_processed=result.active_ideas_processed,
        stage_transitions=result.stage_transitions,
        exhaustion_warnings=result.exhaustion_warnings,
        stop_violations=result.stop_violations,
        snapshots_written=result.snapshots_written,
    )
