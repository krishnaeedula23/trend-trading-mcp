"""Scheduled task endpoints for daily trading touchpoints.

Each endpoint is designed to be triggered by an external cron scheduler
(Railway cron, Supabase pg_cron, or similar). They fetch current data,
format messages, and post to Slack.

PST Schedule:
  5:30am  - morning_brief
  6:40am  - orb_marker
  7:00am  - trend_time
  8:20am  - euro_close
  9:30am  - midday_nudge
  1:00pm  - journal_prompt
  5:00pm  - next_day_prep
  Fri 1pm - weekly_review
"""

import logging
from fastapi import APIRouter

from api.integrations.slack import send_message, format_simple_alert, format_morning_brief, format_journal_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduled", tags=["scheduled"])


@router.post("/morning-brief")
async def morning_brief():
    """5:30am PST — Pre-market analysis and key levels."""
    # TODO: Fetch real data from Saty API (ATR levels, ribbon, phase, VIX, structure)
    plan_data = {
        "ticker": "SPY",
        "structural_bias": "Pending analysis",
        "vix_reading": "N/A",
        "key_levels": "Pending analysis",
    }
    text = format_morning_brief(plan_data)
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/orb-marker")
async def orb_marker():
    """6:40am PST — Log 10-min Opening Range High/Low."""
    text = format_simple_alert(
        "ORB Marked",
        "10-minute Opening Range is set. Look for break and retest setups."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/trend-time")
async def trend_time():
    """7:00am PST — Trend time alert."""
    text = format_simple_alert(
        "Trend Time",
        "Ribbon should be establishing direction. Look for Flag Into Ribbon and continuation setups."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/euro-close")
async def euro_close():
    """8:20am PST — Euro close warning."""
    text = format_simple_alert(
        "Euro Close in 10 Minutes",
        "Euro close at 8:30am PST. Watch for reversals and volatility shift."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/midday-nudge")
async def midday_nudge():
    """9:30am PST — Break reminder with session stats."""
    # TODO: Fetch today's trade stats from Supabase
    text = format_simple_alert(
        "Midday Break",
        "Break time. Step away from charts. There's always another trade."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/journal-prompt")
async def journal_prompt():
    """1:00pm PST — End-of-day journal prompt."""
    # TODO: Fetch today's trade stats from Supabase
    stats = {"total_trades": 0, "total_pnl": 0, "total_r": 0}
    text = format_journal_prompt(stats)
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/next-day-prep")
async def next_day_prep():
    """5:00pm PST — Key levels and setups for tomorrow."""
    text = format_simple_alert(
        "Next-Day Prep",
        "Time to prep charts for tomorrow. Mark key levels and identify potential setups."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/weekly-review")
async def weekly_review():
    """Friday 1:00pm PST — Auto-generated weekly performance review."""
    # TODO: Fetch weekly stats from Supabase, compute analytics
    text = format_simple_alert(
        "Weekly Review",
        "Weekly review generation coming soon. Check your analytics dashboard."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}
