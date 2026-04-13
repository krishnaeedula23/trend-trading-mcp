"""TradingView webhook receiver — validates and accepts setup alerts."""

import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class TradingViewPayload(BaseModel):
    ticker: str
    timeframe: str
    setup: str
    direction: str = Field(..., description="long or short")
    price: float
    alert: str = ""


@router.post("/tradingview")
async def tradingview_webhook(
    payload: TradingViewPayload,
    token: str = Query(..., description="Webhook secret token"),
):
    """Receive TradingView alert, validate token and setup type."""
    secret = os.environ.get("TRADINGVIEW_WEBHOOK_SECRET", "")
    if not secret or token != secret:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    # Validate setup type
    from api.indicators.satyland.setups import registered_setups
    valid = registered_setups()
    if payload.setup not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setup: {payload.setup}. Valid: {valid}",
        )

    # Normalize direction
    direction = "bullish" if payload.direction == "long" else "bearish"

    # TODO Task 4.2: fetch indicators, grade setup, post to Slack, save to Supabase
    return {
        "status": "received",
        "ticker": payload.ticker,
        "setup": payload.setup,
        "direction": direction,
        "price": payload.price,
        "grade": "pending",
    }
