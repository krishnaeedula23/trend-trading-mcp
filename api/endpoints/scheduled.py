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
  1:15pm  - alert_review
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
            # Pre-market: compute actual distance from PDC as % of ATR (not yesterday's range)
            premarket_dist = abs(current - pdc) if current and pdc else 0
            atr_pct = round(premarket_dist / atr_val * 100, 1) if atr_val > 0 else 0
            levels = atr_result.get("levels", {})

            # Build MTF ribbon grid — EMA 21, ribbon state, phase, bias candle per TF
            def _ribbon_row(tf_name, ribbon_data, phase_data=None):
                state = ribbon_data.get("ribbon_state", "?")
                state_emoji = {"bullish": "🟢", "bearish": "🔴", "chopzilla": "🟡"}.get(state, "⚪")
                candle = ribbon_data.get("bias_candle", "?")
                candle_emoji = {"green": "🟢", "blue": "🔵", "red": "🔴", "orange": "🟠", "gray": "⚪"}.get(candle, "⚪")
                ema21 = ribbon_data.get("ema21", 0)
                dist = current - ema21 if ema21 else 0
                dist_pct = (dist / ema21 * 100) if ema21 else 0
                # Phase for this TF
                po_text = ""
                if phase_data:
                    po_val = phase_data.get("oscillator", 0)
                    po_phase = phase_data.get("phase", "?")
                    po_emoji = {"green": "🟢", "red": "🔴", "compression": "🟣"}.get(po_phase, "⚪")
                    po_text = f"  |  PO: {po_emoji} {po_val:+.1f}"
                return (
                    f"  `{tf_name:>3}` {state_emoji} {state:<10} "
                    f"Candle: {candle_emoji}  |  "
                    f"EMA21: `{ema21:.2f}` ({dist:+.2f}, {dist_pct:+.2f}%)"
                    f"{po_text}"
                )

            # Compute phase for each TF
            phase_5m = phase_oscillator(three_min_df)
            phase_15m = phase_oscillator(ten_min_df)
            phase_1h = phase_result

            mtf_grid = "\n".join([
                _ribbon_row("5m", ribbon_3m, phase_5m),
                _ribbon_row("15m", ribbon_10m, phase_15m),
                _ribbon_row("1h", ribbon_1h, phase_1h),
            ])

            # Emojis
            bias = structure_result.get("structural_bias", "unknown").replace("_", " ").title()
            bias_emoji = {"Strongly Bullish": "🟢🟢", "Bullish": "🟢", "Neutral": "⚪", "Bearish": "🔴", "Strongly Bearish": "🔴🔴"}.get(bias, "⚪")
            phase_state = phase_result.get("phase", "unknown").title()
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

                f"*🎯 Overview*\n"
                f"  Structural Bias:  {bias_emoji} {bias}\n"
                f"  MTF Conviction:   {conviction} (score: {mtf_result.get('min_score', 'N/A')})\n\n"

                f"*📏 Multi-Timeframe Ribbon*\n"
                f"{mtf_grid}\n\n"

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


@router.post("/alert-review")
async def alert_review():
    """1:15pm PST — Post-market review of today's alerts vs actual price action."""
    import asyncio
    import datetime

    today = datetime.date.today().isoformat()
    alerts_data = []

    # 1. Fetch today's alerts from Supabase
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("trading_alerts").select("*").eq("date", today).execute()
        alerts_data = result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch alerts: {e}")
        text = format_simple_alert("Alert Review", f"Failed to fetch alerts: {e}")
        await send_message(text)
        return {"status": "error", "error": str(e)}

    if not alerts_data:
        text = format_simple_alert("Alert Review", "No alerts fired today.")
        await send_message(text)
        return {"status": "sent", "message": text, "alerts_reviewed": 0}

    # 2. Analyze each alert
    from api.endpoints.satyland import _fetch_intraday
    from api.indicators.satyland.atr_levels import atr_levels
    from api.endpoints.satyland import _fetch_daily

    # Map TradingView futures/index symbols to yfinance equivalents
    TICKER_MAP = {
        "ES1!": "ES=F", "NQ1!": "NQ=F", "CL1!": "CL=F", "GC1!": "GC=F",
        "RTY1!": "RTY=F", "YM1!": "YM=F", "ZB1!": "ZB=F",
        "US500": "^GSPC", "US100": "^NDX", "US30": "^DJI",
        "VIX": "^VIX", "DXY": "DX-Y.NYB",
    }

    reviews = []
    for alert in alerts_data:
        tv_ticker = alert.get("ticker", "SPY")
        ticker = TICKER_MAP.get(tv_ticker, tv_ticker)  # Map to yfinance symbol
        setup_type = alert.get("setup_type", "unknown")
        direction = alert.get("direction", "bullish")
        alert_grade = alert.get("grade", "?")
        details = alert.get("details", {})

        # Extract alert price — check both old and new detail formats
        alert_price = 0
        if isinstance(details, dict):
            raw = details.get("raw_payload", {})
            if isinstance(raw, dict):
                alert_price = raw.get("price", 0) or 0
            # Also check grade_result for nested raw_payload
            grade_res = details.get("grade_result", {})
            if not alert_price and isinstance(grade_res, dict):
                alert_price = grade_res.get("price", 0) or 0
            # Direct price field
            if not alert_price:
                alert_price = details.get("price", 0) or 0

        try:
            # Fetch 5-minute data (more reliable than 1m after close)
            df = await asyncio.to_thread(_fetch_intraday, ticker, "5m")
            if df is None or df.empty:
                detail = f"No data for {tv_ticker}" if tv_ticker != ticker else "Could not fetch price data"
                reviews.append({
                    "ticker": tv_ticker, "setup": setup_type, "direction": direction,
                    "grade": alert_grade, "alert_price": alert_price,
                    "result": "no_data", "detail": detail,
                })
                continue

            # If no alert price, use session open as proxy
            if not alert_price:
                alert_price = float(df["open"].iloc[0])

            # Get daily ATR and ribbon for realistic stop/target
            daily_df = await asyncio.to_thread(_fetch_daily, ticker)
            atr_result = atr_levels(daily_df)
            atr_val = atr_result.get("atr", 0)

            # Compute ribbon on 5m to get EMA 21 (the pivot) for stop reference
            from api.indicators.satyland.pivot_ribbon import pivot_ribbon
            ribbon = pivot_ribbon(df)
            ema21 = ribbon.get("ema21", 0)
            ema48 = ribbon.get("ema48", 0)

            is_bull = direction == "bullish"

            # Stop: other side of ribbon (EMA 48 for most setups)
            # Target: 1R from entry (risk = distance to stop)
            if is_bull:
                stop = ema48 if ema48 and ema48 < alert_price else alert_price - atr_val * 0.236
                risk = abs(alert_price - stop)
                target = alert_price + risk  # 1R target
            else:
                stop = ema48 if ema48 and ema48 > alert_price else alert_price + atr_val * 0.236
                risk = abs(stop - alert_price)
                target = alert_price - risk  # 1R target

            # Ensure minimum risk to avoid division by zero / huge R
            min_risk = alert_price * 0.002  # 0.2% minimum risk
            if risk < min_risk:
                risk = min_risk
                if is_bull:
                    stop = alert_price - risk
                    target = alert_price + risk
                else:
                    stop = alert_price + risk
                    target = alert_price - risk

            # Analyze price action from the session
            closes = df["close"].values
            highs = df["high"].values
            lows = df["low"].values

            if is_bull:
                max_favorable = float(max(highs)) if len(highs) > 0 else alert_price
                max_adverse = float(min(lows)) if len(lows) > 0 else alert_price
                hit_target = max_favorable >= target
                hit_stop = max_adverse <= stop
            else:
                max_favorable = float(min(lows)) if len(lows) > 0 else alert_price
                max_adverse = float(max(highs)) if len(highs) > 0 else alert_price
                hit_target = max_favorable <= target
                hit_stop = max_adverse >= stop

            # Determine outcome
            if hit_target and not hit_stop:
                outcome = "Winner"
                outcome_emoji = "✅"
            elif hit_stop and not hit_target:
                outcome = "Loser"
                outcome_emoji = "❌"
            elif hit_target and hit_stop:
                outcome = "Mixed"
                outcome_emoji = "⚠️"
            else:
                outcome = "No Fill"
                outcome_emoji = "⏳"

            # R-multiples from alert price
            if is_bull:
                best_r = round((max_favorable - alert_price) / risk, 1) if risk > 0 else 0
            else:
                best_r = round((alert_price - max_favorable) / risk, 1) if risk > 0 else 0

            session_close = float(closes[-1]) if len(closes) > 0 else alert_price
            if is_bull:
                eod_r = round((session_close - alert_price) / risk, 1) if risk > 0 else 0
            else:
                eod_r = round((alert_price - session_close) / risk, 1) if risk > 0 else 0

            reviews.append({
                "ticker": ticker,
                "setup": setup_type,
                "direction": direction,
                "grade": alert_grade,
                "alert_price": round(alert_price, 2),
                "target": round(target, 2),
                "stop": round(stop, 2),
                "max_favorable": round(max_favorable, 2),
                "max_adverse": round(max_adverse, 2),
                "session_close": round(session_close, 2),
                "best_r": round(best_r, 2),
                "eod_r": round(eod_r, 2),
                "result": outcome,
                "result_emoji": outcome_emoji,
                "alert_id": alert.get("id"),
            })

        except Exception as e:
            logger.warning(f"Alert review failed for {ticker} {setup_type}: {e}")
            reviews.append({
                "ticker": ticker, "setup": setup_type, "direction": direction,
                "grade": alert_grade, "alert_price": alert_price,
                "result": "error", "detail": str(e),
            })

    # 3. Build Slack summary
    winners = [r for r in reviews if r["result"] == "Winner"]
    losers = [r for r in reviews if r["result"] == "Loser"]
    total = len(reviews)

    header = (
        f"{'─' * 40}\n"
        f"📊  *POST-MARKET ALERT REVIEW*\n"
        f"{'─' * 40}\n\n"
        f"Alerts today: *{total}*  |  "
        f"✅ Winners: *{len(winners)}*  |  "
        f"❌ Losers: *{len(losers)}*\n\n"
    )

    details_text = ""
    for r in reviews:
        if r["result"] in ("no_data", "error"):
            details_text += f"  ⚪ {r['ticker']} {r['setup'].replace('_', ' ').title()} — {r.get('detail', 'error')}\n"
            continue

        emoji = r.get("result_emoji", "?")
        setup_display = r["setup"].replace("_", " ").title()
        dir_label = "Long" if r["direction"] == "bullish" else "Short"

        details_text += (
            f"  {emoji} *{r['ticker']}* {setup_display} ({dir_label}) — Grade: {r['grade']}\n"
            f"      Alert: {r['alert_price']}  |  Target: {r['target']}  |  Stop: {r['stop']}\n"
            f"      Best: {r['max_favorable']} ({r['best_r']:+.1f}R)  |  Close: {r['session_close']} ({r['eod_r']:+.1f}R)\n"
            f"      Result: *{r['result']}*\n\n"
        )

    # Lesson summary
    lesson = ""
    if winners and losers:
        lesson = f"\n_Review: {len(winners)}/{total} alerts played out. Check the losers — did the thesis break or was timing off?_"
    elif winners and not losers:
        lesson = f"\n_All {len(winners)} alerts were winners. Trust the system._"
    elif losers and not winners:
        lesson = f"\n_Tough day — {len(losers)} alerts didn't work. Review conditions and filters._"

    text = header + details_text + f"{'─' * 40}" + lesson
    sent = await send_message(text)

    # 4. Update alert records in Supabase with review data
    try:
        sb = get_supabase()
        for r in reviews:
            if r.get("alert_id") and r["result"] not in ("no_data", "error"):
                sb.table("trading_alerts").update({
                    "details": {
                        **(alerts_data[reviews.index(r)].get("details") or {}),
                        "review": {
                            "result": r["result"],
                            "target": r.get("target"),
                            "stop": r.get("stop"),
                            "max_favorable": r.get("max_favorable"),
                            "max_adverse": r.get("max_adverse"),
                            "session_close": r.get("session_close"),
                            "best_r": r.get("best_r"),
                            "eod_r": r.get("eod_r"),
                        },
                    },
                }).eq("id", r["alert_id"]).execute()
    except Exception as e:
        logger.warning(f"Failed to update alert reviews: {e}")

    return {"status": "sent" if sent else "slack_not_configured", "alerts_reviewed": total, "reviews": reviews}
