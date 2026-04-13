"""TradingView webhook receiver — validates and accepts setup alerts."""

import asyncio
import datetime
import logging
import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

# Map minute-string timeframes to yfinance-compatible keys (same as mtf-score endpoint)
_MINUTE_TO_TF: dict[str, str] = {
    "1": "1m",
    "3": "5m",   # yfinance has no 3m; use 5m as nearest proxy
    "5": "5m",
    "10": "15m",  # nearest proxy
    "15": "15m",
    "30": "1h",   # nearest proxy
    "60": "1h",
    "240": "4h",
    "1d": "1d",
    "1w": "1w",
}


class TradingViewPayload(BaseModel):
    ticker: str
    timeframe: str
    setup: str
    direction: str = Field(..., description="long or short")
    price: float
    alert: str = ""


def _resolve_timeframe(timeframe: str) -> str:
    """Convert a webhook timeframe string to a yfinance-compatible key."""
    if timeframe in _MINUTE_TO_TF:
        return _MINUTE_TO_TF[timeframe]
    # Already a valid key (e.g. "1m", "5m")
    return timeframe


@router.post("/tradingview")
async def tradingview_webhook(
    payload: TradingViewPayload,
    token: str = Query(..., description="Webhook secret token"),
):
    """Receive TradingView alert, grade setup, post to Slack, save to Supabase."""
    # 1. Validate token
    import hmac
    secret = os.environ.get("TRADINGVIEW_WEBHOOK_SECRET", "")
    if not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    from api.indicators.satyland.setups import registered_setups
    valid = registered_setups()
    if payload.setup not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown setup: {payload.setup}")

    direction = "bullish" if payload.direction == "long" else "bearish"
    alert_id = None

    # 2. Persist immediately (persist-first)
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        alert_record = sb.table("alerts").insert({
            "date": datetime.date.today().isoformat(),
            "ticker": payload.ticker,
            "setup_type": payload.setup,
            "direction": direction,
            "timeframe": payload.timeframe,
            "alert_type": "webhook",
            "grade": "pending",
            "details": {"raw_payload": payload.model_dump()},
        }).execute()
        alert_id = alert_record.data[0]["id"] if alert_record.data else None
    except Exception as e:
        logger.warning(f"Failed to persist alert: {e}")

    # 3. Fetch indicators + grade
    grade_result = None
    try:
        from api.endpoints.satyland import (
            _fetch_daily,
            _fetch_intraday,
            _normalise_columns,
        )
        from api.indicators.satyland.atr_levels import atr_levels
        from api.indicators.satyland.phase_oscillator import phase_oscillator
        from api.indicators.satyland.pivot_ribbon import pivot_ribbon
        from api.indicators.satyland.price_structure import price_structure
        from api.indicators.satyland.setup_grader import grade_setup
        from api.indicators.satyland.mtf_score import mtf_score, aggregate_mtf_scores

        tf_key = _resolve_timeframe(payload.timeframe)

        intraday_df = await asyncio.to_thread(_fetch_intraday, payload.ticker, tf_key)
        daily_df = await asyncio.to_thread(_fetch_daily, payload.ticker)

        atr_result = atr_levels(daily_df, intraday_df)
        ribbon_result = pivot_ribbon(intraday_df)
        phase_result = phase_oscillator(intraday_df)
        structure_result = price_structure(daily_df)

        # Compute MTF score for the current timeframe
        current_score = mtf_score(intraday_df)
        tf_label = f"{payload.timeframe}m" if payload.timeframe.isdigit() else payload.timeframe
        mtf_scores = aggregate_mtf_scores({tf_label: current_score})

        grade_result = grade_setup(
            setup_type=payload.setup,
            direction=direction,
            atr=atr_result,
            ribbon=ribbon_result,
            phase=phase_result,
            structure=structure_result,
            mtf_scores=mtf_scores,
        )
    except Exception as e:
        logger.error(f"Grading failed: {e}")
        grade_result = {"grade": "error", "reasoning": str(e)}

    # 4. Post to Slack
    try:
        from api.integrations.slack import format_setup_alert, send_message
        if grade_result and grade_result.get("grade") != "error":
            text = format_setup_alert(grade_result, payload.ticker, payload.timeframe, payload.price)
            await send_message(text)
    except Exception as e:
        logger.warning(f"Slack post failed: {e}")

    # 5. Update alert record with grade
    if alert_id and grade_result:
        try:
            from api.integrations.supabase_client import get_supabase
            sb = get_supabase()
            sb.table("alerts").update({
                "grade": grade_result.get("grade", "error"),
                "details": grade_result,
            }).eq("id", alert_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update alert: {e}")

    return {
        "status": "processed",
        "alert_id": alert_id,
        "ticker": payload.ticker,
        "setup": payload.setup,
        "direction": direction,
        "grade": grade_result.get("grade", "error") if grade_result else "error",
    }
