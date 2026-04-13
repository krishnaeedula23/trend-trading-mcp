"""Trade logging CRUD endpoints."""

import datetime
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trades", tags=["trades"])

VALID_SETUP_TYPES = [
    "orb", "vomy", "ivomy", "flag_into_ribbon", "golden_gate",
    "squeeze", "divergence_from_extreme", "eod_divergence", "wicky_wicky",
]
VALID_STATUSES = ["open", "closed", "stopped_out", "incomplete"]
VALID_DIRECTIONS = ["long", "short"]


class TradeCreate(BaseModel):
    ticker: str
    direction: str = Field(..., description="long or short")
    setup_type: str
    instrument: str | None = None  # e.g. "SPY 560C 0DTE"
    trigger: str | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    sizing: int | None = None
    risk_amount: float | None = None
    grade: str | None = None
    green_flags: dict | None = None
    mtf_scores: dict | None = None
    probability: float | None = None
    reasoning: str | None = None
    notes: str | None = None
    alert_id: str | None = None


class TradeUpdate(BaseModel):
    exit_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    status: str | None = None
    pnl: float | None = None
    r_multiple: float | None = None
    notes: str | None = None


@router.post("")
async def create_trade(trade: TradeCreate):
    """Create a new trade entry."""
    if trade.direction not in VALID_DIRECTIONS:
        raise HTTPException(400, f"Invalid direction: {trade.direction}. Use: {VALID_DIRECTIONS}")
    if trade.setup_type not in VALID_SETUP_TYPES:
        raise HTTPException(400, f"Invalid setup_type: {trade.setup_type}. Use: {VALID_SETUP_TYPES}")

    # Determine status
    status = "open"
    missing_fields = []
    if not trade.entry_price:
        missing_fields.append("entry_price")
    if not trade.stop_price:
        missing_fields.append("stop_price")
    if not trade.target_price:
        missing_fields.append("target_price")
    if not trade.sizing:
        missing_fields.append("sizing")
    if missing_fields:
        status = "incomplete"

    record = {
        "date": datetime.date.today().isoformat(),
        "ticker": trade.ticker,
        "direction": trade.direction,
        "setup_type": trade.setup_type,
        "instrument": trade.instrument,
        "trigger": trade.trigger,
        "entry_price": trade.entry_price,
        "stop_price": trade.stop_price,
        "target_price": trade.target_price,
        "sizing": trade.sizing,
        "risk_amount": trade.risk_amount,
        "status": status,
        "grade": trade.grade,
        "green_flags": trade.green_flags,
        "mtf_scores": trade.mtf_scores,
        "probability": trade.probability,
        "reasoning": trade.reasoning,
        "notes": trade.notes,
        "alert_id": trade.alert_id,
        "entered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("trades").insert(record).execute()
        return {"status": "created", "trade": result.data[0] if result.data else record, "missing_fields": missing_fields}
    except RuntimeError:
        # Supabase not configured — return the record anyway for testing
        logger.warning("Supabase not configured, returning unsaved record")
        return {"status": "not_saved", "trade": record, "missing_fields": missing_fields}


@router.patch("/{trade_id}")
async def update_trade(trade_id: str, update: TradeUpdate):
    """Update an existing trade (exit, status change, etc.)."""
    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "No fields to update")

    if "status" in changes and changes["status"] not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status: {changes['status']}")

    if "exit_price" in changes:
        changes["exited_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if "status" not in changes:
            changes["status"] = "closed"

    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("trades").update(changes).eq("id", trade_id).execute()
        return {"status": "updated", "trade": result.data[0] if result.data else changes}
    except RuntimeError:
        logger.warning("Supabase not configured")
        return {"status": "not_saved", "changes": changes}


@router.get("")
async def list_trades(date: str | None = None, status: str | None = None):
    """List trades, optionally filtered by date and status."""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        query = sb.table("trades").select("*").order("entered_at", desc=True)
        if date:
            query = query.eq("date", date)
        if status:
            query = query.eq("status", status)
        result = query.limit(50).execute()
        return {"trades": result.data}
    except RuntimeError:
        return {"trades": [], "error": "Supabase not configured"}


@router.get("/{trade_id}")
async def get_trade(trade_id: str):
    """Get a single trade by ID."""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("trades").select("*").eq("id", trade_id).execute()
        if not result.data:
            raise HTTPException(404, "Trade not found")
        return {"trade": result.data[0]}
    except RuntimeError:
        raise HTTPException(503, "Supabase not configured")


@router.post("/from-alert/{alert_id}")
async def create_from_alert(alert_id: str, trade: TradeCreate):
    """Create a trade pre-filled from an alert (the 'take' reply flow)."""
    trade.alert_id = alert_id
    # Pre-fill from alert if we can fetch it
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        alert = sb.table("alerts").select("*").eq("id", alert_id).execute()
        if alert.data:
            alert_data = alert.data[0]
            # Pre-fill from alert details
            if not trade.setup_type:
                trade.setup_type = alert_data.get("setup_type", trade.setup_type)
            if not trade.grade and alert_data.get("grade"):
                trade.grade = alert_data["grade"]
    except Exception as e:
        logger.warning(f"Could not fetch alert {alert_id}: {e}")

    result = await create_trade(trade)

    # Link alert to trade
    if result.get("trade", {}).get("id"):
        try:
            from api.integrations.supabase_client import get_supabase
            sb = get_supabase()
            sb.table("alerts").update({
                "traded": True,
                "trade_id": result["trade"]["id"],
            }).eq("id", alert_id).execute()
        except Exception:
            pass

    return result
