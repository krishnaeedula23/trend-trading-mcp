"""Post-market Railway endpoint.

POST /api/swing/pipeline/postmarket  (bearer-protected; called by daily-dispatcher at 21:00 UTC)

/universe-refresh will be added by Plan 4 Task 6 once the helper exists.
"""
from __future__ import annotations

import functools
import logging
import os

from fastapi import APIRouter, Depends
from supabase import Client, create_client

from api.endpoints.swing_auth import require_swing_token
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
def trigger_postmarket(_token: None = Depends(require_swing_token)) -> PostmarketRunResponse:
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
