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
    """5:30am PST — Pre-market analysis and key levels for SPY and SPX."""
    import asyncio
    import datetime

    tickers = ["SPY", "^GSPC"]  # SPY + SPX (S&P 500 index)
    ticker_labels = {"SPY": "SPY", "^GSPC": "SPX"}
    messages = []

    # Fetch VIX once (shared across both)
    vix_reading = "N/A"
    try:
        from api.endpoints.satyland import _fetch_daily
        vix_df = await asyncio.to_thread(_fetch_daily, "^VIX")
        vix_reading = round(float(vix_df["close"].iloc[-1]), 2)
    except Exception:
        pass

    for ticker in tickers:
        label = ticker_labels.get(ticker, ticker)
        try:
            from api.endpoints.satyland import _fetch_daily, _fetch_intraday, _fetch_premarket
            from api.indicators.satyland.atr_levels import atr_levels
            from api.indicators.satyland.pivot_ribbon import pivot_ribbon
            from api.indicators.satyland.phase_oscillator import phase_oscillator
            from api.indicators.satyland.price_structure import price_structure
            from api.indicators.satyland.mtf_score import mtf_score, aggregate_mtf_scores

            # Fetch data in parallel — daily, 1h, 15m (proxy for 10m), 5m (proxy for 3m), premarket
            # yfinance supports: 1m, 5m, 15m, 1h — no native 3m or 10m
            daily_df, hourly_df, ten_min_df, three_min_df, premarket_df = await asyncio.gather(
                asyncio.to_thread(_fetch_daily, ticker),
                asyncio.to_thread(_fetch_intraday, ticker, "1h"),
                asyncio.to_thread(_fetch_intraday, ticker, "15m"),
                asyncio.to_thread(_fetch_intraday, ticker, "5m"),
                asyncio.to_thread(_fetch_premarket, ticker),
            )

            # Run indicators
            atr_result = atr_levels(daily_df)
            ribbon_1h = pivot_ribbon(hourly_df)
            ribbon_10m = pivot_ribbon(ten_min_df)
            ribbon_3m = pivot_ribbon(three_min_df)
            phase_result = phase_oscillator(hourly_df)
            structure_result = price_structure(daily_df, premarket_df)

            # MTF scores across timeframes
            scores = {}
            for tf_label, tf_df in [("5m", three_min_df), ("15m", ten_min_df), ("1h", hourly_df)]:
                try:
                    scores[tf_label] = mtf_score(tf_df)
                except Exception:
                    pass
            mtf_result = aggregate_mtf_scores(scores) if scores else {"conviction": "N/A", "min_score": "N/A"}

            # Extract key values
            current = atr_result.get("current_price", 0)
            pdc = atr_result.get("pdc", 0)
            atr_val = atr_result.get("atr", 0)
            atr_pct = atr_result.get("atr_covered_pct", 0)
            levels = atr_result.get("levels", {})

            # EMA 21 values on 5m and 15m + distance from price
            ema21_3m = ribbon_3m.get("ema21", 0)  # 5m as proxy
            ema21_10m = ribbon_10m.get("ema21", 0)  # 15m as proxy
            dist_3m = current - ema21_3m if ema21_3m else 0
            dist_10m = current - ema21_10m if ema21_10m else 0
            dist_3m_pct = (dist_3m / ema21_3m * 100) if ema21_3m else 0
            dist_10m_pct = (dist_10m / ema21_10m * 100) if ema21_10m else 0

            # Emojis
            bias = structure_result.get("structural_bias", "unknown").replace("_", " ").title()
            bias_emoji = {"Strongly Bullish": "🟢🟢", "Bullish": "🟢", "Neutral": "⚪", "Bearish": "🔴", "Strongly Bearish": "🔴🔴"}.get(bias, "⚪")
            phase_state = phase_result.get("phase", "unknown").title()
            phase_emoji = {"Green": "🟢", "Red": "🔴", "Compression": "🟣"}.get(phase_state, "⚪")
            ribbon_1h_state = ribbon_1h.get("ribbon_state", "unknown").title()
            vix_emoji = "🟢" if isinstance(vix_reading, (int, float)) and vix_reading < 17 else "🟡" if isinstance(vix_reading, (int, float)) and vix_reading <= 20 else "🔴"
            conviction = mtf_result.get("conviction", "N/A")
            if isinstance(conviction, str):
                conviction = conviction.title()

            # ATR levels
            ct = atr_result.get("call_trigger", 0)
            pt = atr_result.get("put_trigger", 0)
            gg_bull = levels.get("golden_gate_bull", {}).get("price", 0)
            gg_bear = levels.get("golden_gate_bear", {}).get("price", 0)
            mid_bull = levels.get("mid_range_bull", {}).get("price", 0)
            mid_bear = levels.get("mid_range_bear", {}).get("price", 0)
            fr_bull = levels.get("full_range_bull", {}).get("price", 0)
            fr_bear = levels.get("full_range_bear", {}).get("price", 0)

            # Structure
            pdh = structure_result.get("pdh", 0)
            pdl = structure_result.get("pdl", 0)
            pmh = structure_result.get("pmh")
            pml = structure_result.get("pml")

            # Find nearest ATR level to current price
            atr_level_map = {
                "+100% Full Range": fr_bull,
                "+61.8% Mid Range": mid_bull,
                "+38.2% Golden Gate": gg_bull,
                "+23.6% Call Trigger": ct,
                "0% PDC": pdc,
                "-23.6% Put Trigger": pt,
                "-38.2% Golden Gate": gg_bear,
                "-61.8% Mid Range": mid_bear,
                "-100% Full Range": fr_bear,
            }
            nearest_name = ""
            nearest_price = 0
            nearest_dist = float("inf")
            for name, lvl in atr_level_map.items():
                if lvl and abs(current - lvl) < abs(nearest_dist):
                    nearest_dist = current - lvl
                    nearest_name = name
                    nearest_price = lvl
            nearest_pct = (nearest_dist / nearest_price * 100) if nearest_price else 0
            nearest_text = f"  Nearest ATR Level: *{nearest_name}* ({nearest_price:.2f}) — {'above' if nearest_dist >= 0 else 'below'} by {abs(nearest_dist):.2f} ({nearest_pct:+.2f}%)"

            # Distance emoji (close = within 0.1%, moderate = within 0.3%)
            def dist_emoji(pct):
                abs_pct = abs(pct)
                if abs_pct <= 0.1:
                    return "🎯"  # at the level
                elif abs_pct <= 0.3:
                    return "📍"  # close
                return ""

            text = (
                f"{'─' * 40}\n"
                f"☀️  *MORNING BRIEF — {label}*\n"
                f"{'─' * 40}\n\n"

                f"*📊 Market Snapshot*\n"
                f"  Price: *{current:.2f}*  |  ATR: {atr_val:.2f}  |  Room: {100 - atr_pct:.0f}% remaining\n"
                f"{nearest_text}\n"
                f"  VIX: {vix_emoji} {vix_reading}\n\n"

                f"*🎯 Indicators*\n"
                f"  Structural Bias:  {bias_emoji} {bias}\n"
                f"  Ribbon (1h):      {ribbon_1h_state}\n"
                f"  Phase Oscillator: {phase_emoji} {phase_state}\n"
                f"  MTF Conviction:   {conviction} (score: {mtf_result.get('min_score', 'N/A')})\n\n"

                f"*📏 EMA 21 Proximity*\n"
                f"  5m  EMA 21: `{ema21_3m:>8.2f}`  |  Price {'above' if dist_3m >= 0 else 'below'} by {abs(dist_3m):.2f} ({dist_3m_pct:+.2f}%) {dist_emoji(dist_3m_pct)}\n"
                f"  15m EMA 21: `{ema21_10m:>8.2f}`  |  Price {'above' if dist_10m >= 0 else 'below'} by {abs(dist_10m):.2f} ({dist_10m_pct:+.2f}%) {dist_emoji(dist_10m_pct)}\n\n"

                f"*📐 ATR Levels*\n"
                f"  `+100%  Full Range   {fr_bull:>8.2f}`\n"
                f"  `+61.8% Mid Range    {mid_bull:>8.2f}`\n"
                f"  `+38.2% Golden Gate  {gg_bull:>8.2f}`\n"
                f"  `+23.6% Call Trigger {ct:>8.2f}`\n"
                f"  ` 0.0%  PDC          {pdc:>8.2f}`  ← Zero Line\n"
                f"  `-23.6% Put Trigger  {pt:>8.2f}`\n"
                f"  `-38.2% Golden Gate  {gg_bear:>8.2f}`\n"
                f"  `-61.8% Mid Range    {mid_bear:>8.2f}`\n"
                f"  `-100%  Full Range   {fr_bear:>8.2f}`\n\n"

                f"*🏗️ Structure*\n"
                f"  `PDH  {pdh:>8.2f}`  |  `PDL  {pdl:>8.2f}`\n"
            )
            if pmh and pml:
                text += f"  `PMH  {pmh:>8.2f}`  |  `PML  {pml:>8.2f}`\n"
            text += (
                f"\n{'─' * 40}\n"
                f"_Be patient. Follow your playbook. There's always another trade._"
            )

            messages.append(text)

            # Save to Supabase daily_plans
            try:
                from api.integrations.supabase_client import get_supabase
                sb = get_supabase()
                sb.table("daily_plans").upsert({
                    "date": datetime.date.today().isoformat(),
                    "ticker": label,
                    "structural_bias": structure_result.get("structural_bias"),
                    "atr_levels": atr_result,
                    "ribbon_state": ribbon_1h.get("ribbon_state"),
                    "phase_state": phase_result.get("phase"),
                    "vix_reading": vix_reading if isinstance(vix_reading, (int, float)) else None,
                    "mtf_scores": mtf_result,
                    "key_levels": {
                        "ema21_3m": ema21_3m, "ema21_10m": ema21_10m,
                        "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
                    },
                }, on_conflict="date,ticker").execute()
            except Exception as e:
                logger.warning(f"Failed to save daily plan for {label}: {e}")

        except Exception as e:
            logger.error(f"Morning brief failed for {label}: {e}")
            messages.append(f"☀️ *MORNING BRIEF — {label}*\n\nData fetch failed: {e}")

    # Send each ticker as a separate Slack message
    all_sent = True
    for msg in messages:
        sent = await send_message(msg)
        if not sent:
            all_sent = False

    return {"status": "sent" if all_sent else "partial", "tickers": list(ticker_labels.values()), "messages": messages}


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
