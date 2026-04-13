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
    """5:30am PST — Pre-market analysis and key levels for SPY."""
    import asyncio

    ticker = "SPY"

    try:
        from api.endpoints.satyland import _fetch_daily, _fetch_intraday, _fetch_premarket
        from api.indicators.satyland.atr_levels import atr_levels
        from api.indicators.satyland.pivot_ribbon import pivot_ribbon
        from api.indicators.satyland.phase_oscillator import phase_oscillator
        from api.indicators.satyland.price_structure import price_structure
        from api.indicators.satyland.mtf_score import mtf_score, aggregate_mtf_scores

        # Fetch data in parallel
        daily_df, hourly_df, premarket_df = await asyncio.gather(
            asyncio.to_thread(_fetch_daily, ticker),
            asyncio.to_thread(_fetch_intraday, ticker, "1h"),
            asyncio.to_thread(_fetch_premarket, ticker),
        )

        # Run indicators
        atr_result = atr_levels(daily_df)
        ribbon_result = pivot_ribbon(hourly_df)
        phase_result = phase_oscillator(hourly_df)
        structure_result = price_structure(daily_df, premarket_df)

        # MTF scores on hourly
        hourly_score = mtf_score(hourly_df)
        mtf_result = aggregate_mtf_scores({"1h": hourly_score})

        # VIX
        try:
            vix_df = await asyncio.to_thread(_fetch_daily, "^VIX")
            vix_reading = round(float(vix_df["close"].iloc[-1]), 2)
        except Exception:
            vix_reading = "N/A"

        # Build key levels string
        key_levels_parts = []
        if atr_result.get("call_trigger"):
            key_levels_parts.append(f"Call Trigger: {atr_result['call_trigger']:.2f}")
        if atr_result.get("put_trigger"):
            key_levels_parts.append(f"Put Trigger: {atr_result['put_trigger']:.2f}")
        if atr_result.get("pdc"):
            key_levels_parts.append(f"PDC: {atr_result['pdc']:.2f}")
        levels = atr_result.get("levels", {})
        if levels.get("golden_gate_bull"):
            key_levels_parts.append(f"GG+: {levels['golden_gate_bull']['price']:.2f}")
        if levels.get("golden_gate_bear"):
            key_levels_parts.append(f"GG-: {levels['golden_gate_bear']['price']:.2f}")
        if levels.get("mid_range_bull"):
            key_levels_parts.append(f"Mid+: {levels['mid_range_bull']['price']:.2f}")
        if levels.get("mid_range_bear"):
            key_levels_parts.append(f"Mid-: {levels['mid_range_bear']['price']:.2f}")
        if structure_result.get("pdh"):
            key_levels_parts.append(f"PDH: {structure_result['pdh']:.2f}")
        if structure_result.get("pdl"):
            key_levels_parts.append(f"PDL: {structure_result['pdl']:.2f}")
        if structure_result.get("pmh"):
            key_levels_parts.append(f"PMH: {structure_result['pmh']:.2f}")
        if structure_result.get("pml"):
            key_levels_parts.append(f"PML: {structure_result['pml']:.2f}")

        # Build the detailed brief
        bias = structure_result.get("structural_bias", "unknown").replace("_", " ").title()
        ribbon_state = ribbon_result.get("ribbon_state", "unknown").title()
        phase_state = phase_result.get("phase", "unknown").title()
        conviction = mtf_result.get("conviction", "unknown").title()
        atr_val = atr_result.get("atr", 0)
        atr_pct = atr_result.get("atr_covered_pct", 0)
        current = atr_result.get("current_price", 0)

        text = (
            f"☀️ *Morning Brief — {ticker}*\n\n"
            f"*Price:* {current:.2f} | *ATR:* {atr_val:.2f} ({atr_pct:.0f}% consumed)\n"
            f"*Structural Bias:* {bias}\n"
            f"*Ribbon (1h):* {ribbon_state} | *Phase:* {phase_state}\n"
            f"*MTF Conviction:* {conviction} (score: {mtf_result.get('min_score', 'N/A')})\n"
            f"*VIX:* {vix_reading}\n\n"
            f"*Key Levels:*\n" + "\n".join(f"  • {l}" for l in key_levels_parts) + "\n\n"
            f"Good luck today. Be patient. Follow your playbook."
        )

    except Exception as e:
        logger.error(f"Morning brief data fetch failed: {e}")
        text = format_morning_brief({
            "ticker": ticker,
            "structural_bias": f"Error: {e}",
            "vix_reading": "N/A",
            "key_levels": "Data fetch failed",
        })

    # Save to Supabase daily_plans
    try:
        from api.integrations.supabase_client import get_supabase
        import datetime
        sb = get_supabase()
        sb.table("daily_plans").upsert({
            "date": datetime.date.today().isoformat(),
            "ticker": ticker,
            "structural_bias": structure_result.get("structural_bias", "unknown") if 'structure_result' in dir() else None,
            "atr_levels": atr_result if 'atr_result' in dir() else None,
            "ribbon_state": ribbon_result.get("ribbon_state") if 'ribbon_result' in dir() else None,
            "phase_state": phase_result.get("phase") if 'phase_result' in dir() else None,
            "vix_reading": vix_reading if isinstance(vix_reading, (int, float)) else None,
            "mtf_scores": mtf_result if 'mtf_result' in dir() else None,
        }, on_conflict="date,ticker").execute()
    except Exception as e:
        logger.warning(f"Failed to save daily plan: {e}")

    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/orb-marker")
async def orb_marker():
    """6:40am PST — Log 10-min Opening Range High/Low."""
    import asyncio
    import datetime

    ticker = "SPY"
    or_high = None
    or_low = None

    try:
        from api.endpoints.satyland import _fetch_intraday
        # Fetch 1m data to get the opening range (first 10 minutes)
        df = await asyncio.to_thread(_fetch_intraday, ticker, "1m")
        if df is not None and not df.empty:
            # Get today's bars only
            today = datetime.date.today()
            today_bars = df[df.index.date == today] if hasattr(df.index, 'date') else df
            # First 10 bars of the session (assuming 1m bars)
            if len(today_bars) >= 10:
                or_bars = today_bars.iloc[:10]
                or_high = float(or_bars["high"].max())
                or_low = float(or_bars["low"].min())
    except Exception as e:
        logger.warning(f"Failed to fetch OR data: {e}")

    if or_high and or_low:
        text = format_simple_alert(
            "ORB Marked",
            f"10-min Opening Range set for {ticker}:\n"
            f"  • OR High: {or_high:.2f}\n"
            f"  • OR Low: {or_low:.2f}\n"
            f"  • OR Range: {or_high - or_low:.2f}\n"
            f"  • Midpoint (stop): {(or_high + or_low) / 2:.2f}\n\n"
            f"Look for break and retest setups."
        )

        # Save OR to daily_plans
        try:
            from api.integrations.supabase_client import get_supabase
            sb = get_supabase()
            sb.table("daily_plans").upsert({
                "date": datetime.date.today().isoformat(),
                "ticker": ticker,
                "or_high": or_high,
                "or_low": or_low,
            }, on_conflict="date,ticker").execute()
        except Exception as e:
            logger.warning(f"Failed to save OR: {e}")
    else:
        text = format_simple_alert(
            "ORB Marked",
            "10-minute Opening Range is set. Check your charts for High/Low levels."
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
    import datetime
    stats_text = ""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        today = datetime.date.today().isoformat()
        result = sb.table("trades").select("*").eq("date", today).execute()
        trades = result.data or []
        total = len(trades)
        pnl = sum(t.get("pnl", 0) or 0 for t in trades)
        total_r = sum(t.get("r_multiple", 0) or 0 for t in trades)
        if total > 0:
            stats_text = f"\nSession so far: {total} trades | {total_r:+.1f}R | ${pnl:+.0f} P&L\n"
    except Exception as e:
        logger.warning(f"Failed to fetch trade stats: {e}")

    text = format_simple_alert(
        "Midday Break",
        f"Break time.{stats_text}Step away from charts. There's always another trade."
    )
    sent = await send_message(text)
    return {"status": "sent" if sent else "slack_not_configured", "message": text}


@router.post("/journal-prompt")
async def journal_prompt():
    """1:00pm PST — End-of-day journal prompt with actual stats."""
    import datetime
    stats = {"total_trades": 0, "total_pnl": 0, "total_r": 0}

    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        today = datetime.date.today().isoformat()
        result = sb.table("trades").select("*").eq("date", today).execute()
        trades = result.data or []
        stats["total_trades"] = len(trades)
        stats["total_pnl"] = sum(t.get("pnl", 0) or 0 for t in trades)
        stats["total_r"] = sum(t.get("r_multiple", 0) or 0 for t in trades)

        # Also fetch today's notes to include in prompt
        notes_result = sb.table("notes").select("*").eq("date", today).execute()
        notes = notes_result.data or []
    except Exception as e:
        logger.warning(f"Failed to fetch stats: {e}")
        notes = []

    text = format_journal_prompt(stats)

    # Append mid-session notes if any
    if notes:
        text += "\n\n*Mid-session notes from today:*\n"
        for n in notes:
            cat = n.get("category", "note")
            content = n.get("content", "")
            text += f"  • _{content}_ ({cat})\n"

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
