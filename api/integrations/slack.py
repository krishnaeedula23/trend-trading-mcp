"""Slack message sender and formatter for trading companion alerts."""

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_slack_client():
    """Lazy-load Slack client. Returns None if not configured."""
    try:
        from slack_sdk import WebClient
    except ImportError:
        logger.warning("slack_sdk not installed — Slack messages disabled")
        return None

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        logger.warning("SLACK_BOT_TOKEN not set — Slack messages disabled")
        return None
    return WebClient(token=token)


def _get_channel() -> str:
    return os.environ.get("SLACK_CHANNEL_ID", "")


async def send_message(text: str, blocks: list[dict] | None = None) -> bool:
    """Send a message to the configured Slack channel. Returns True on success."""
    import asyncio

    client = _get_slack_client()
    channel = _get_channel()
    if not client or not channel:
        logger.info("Slack not configured, skipping message")
        return False

    try:
        await asyncio.to_thread(
            client.chat_postMessage,
            channel=channel,
            text=text,
            blocks=blocks,
        )
        return True
    except Exception as e:
        logger.error(f"Slack send failed: {e}")
        return False


def format_setup_alert(grade_result: dict, ticker: str, timeframe: str, price: float) -> str:
    """Format a setup alert for Slack from grade_setup() output."""
    setup = grade_result["setup_type"]
    direction = grade_result["direction"]
    grade = grade_result["grade"]
    prob = grade_result.get("probability", 0)
    prob_source = grade_result.get("probability_source", "estimated")

    emoji = "🟢" if direction == "bullish" else "🔴"
    setup_display = setup.upper().replace("_", " ")

    # Required flags
    req_lines = []
    for f in grade_result.get("required_flags", []):
        icon = "✅" if f["passed"] else "❌"
        req_lines.append(f"  {icon} {f['name']}: {f['reason']}")

    # Bonus flags
    bonus_lines = []
    for f in grade_result.get("bonus_flags", []):
        icon = "✅" if f["passed"] else "⬜"
        bonus_lines.append(f"  {icon} {f['name']}: {f['reason']}")

    bonus_count = sum(1 for f in grade_result.get("bonus_flags", []) if f["passed"])
    total_bonus = len(grade_result.get("bonus_flags", []))

    text = (
        f"{emoji} *{setup_display} — {ticker} {'Long' if direction == 'bullish' else 'Short'} ({timeframe})*\n"
        f"Price: {price}\n\n"
        f"*Required:*\n" + "\n".join(req_lines) + "\n\n"
        f"*Bonus ({bonus_count}/{total_bonus}):*\n" + "\n".join(bonus_lines) + "\n\n"
        f"*Grade: {grade}* | Probability: {prob:.0%} ({prob_source})\n\n"
        f"Reply \"take\" to log entry, or ignore."
    )
    return text


def format_morning_brief(plan_data: dict) -> str:
    """Format the 5:30am PST morning brief."""
    ticker = plan_data.get("ticker", "SPY")
    bias = plan_data.get("structural_bias", "unknown")
    vix = plan_data.get("vix_reading", "N/A")

    return (
        f"☀️ *Morning Brief — {ticker}*\n\n"
        f"*Structural Bias:* {bias}\n"
        f"*VIX:* {vix}\n"
        f"*Key Levels:* {plan_data.get('key_levels', 'N/A')}\n\n"
        f"Good luck today. Be patient. Follow your playbook."
    )


def format_journal_prompt(stats: dict) -> str:
    """Format the 1:00pm PST journal prompt."""
    trades = stats.get("total_trades", 0)
    pnl = stats.get("total_pnl", 0)
    total_r = stats.get("total_r", 0)

    return (
        f"📝 *Session Over — Journal Time*\n"
        f"Today: {trades} trades | {total_r:+.1f}R | ${pnl:+.0f} P&L\n\n"
        f"1. How did you feel today? (focused / anxious / patient / tilted / disciplined)\n"
        f"2. What worked?\n"
        f"3. What didn't?\n"
        f"4. Any rules broken?\n"
        f"5. Lessons for tomorrow?\n\n"
        f"_Reply naturally — I'll structure it for you._"
    )


def format_simple_alert(title: str, message: str) -> str:
    """Format a simple timed alert (ORB, trend time, euro close, etc.)."""
    return f"⏰ *{title}*\n{message}"
