"""Sunday universe-refresh wrapper.

Skips if the latest Deepvue CSV upload is < 7 days old; otherwise calls
Plan 1's generate_backend_universe() and persists via save_universe_batch().
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from api.indicators.swing.universe.generator import generate_backend_universe
from api.indicators.swing.universe.resolver import save_universe_batch

logger = logging.getLogger(__name__)

FRESHNESS_DAYS = 7


class SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


def run_swing_universe_refresh(sb: SupabaseLike) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FRESHNESS_DAYS)

    deepvue_rows = (
        sb.table("swing_universe").select("*")
        .eq("source", "deepvue-csv").is_("removed_at", None)
        .order("added_at", desc=True).limit(1).execute().data or []
    )
    if deepvue_rows:
        latest = deepvue_rows[0]["added_at"]
        latest_dt = latest if isinstance(latest, datetime) else datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
        if latest_dt >= cutoff:
            result = {
                "ran_at": now.isoformat(),
                "skipped": True,
                "skip_reason": f"deepvue-csv upload is {(now - latest_dt).days}d old",
                "base_count": None, "final_count": None, "batch_id": None,
            }
            _post_slack(result)
            return result

    gen = generate_backend_universe()
    tickers_with_extras = {
        t: {"fundamentals": info.get("fundamentals", {})}
        for t, info in gen["passers"].items()
    }
    batch_id = save_universe_batch(sb, tickers_with_extras, source="backend-generated", mode="replace")

    result = {
        "ran_at": now.isoformat(),
        "skipped": False,
        "skip_reason": None,
        "base_count": gen["stats"]["base_count"],
        "final_count": gen["stats"]["final_count"],
        "batch_id": str(batch_id),
    }
    _post_slack(result)
    return result


def _post_slack(result: dict) -> None:
    try:
        from types import SimpleNamespace
        from api.indicators.swing.pipeline.slack import post_weekend_refresh_digest
        post_weekend_refresh_digest(SimpleNamespace(**result))
    except Exception as e:
        logger.warning("Slack digest failed (non-fatal): %s", e)
