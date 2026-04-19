"""Slack digest helpers for post-market + weekend-refresh swing pipelines.

Kept separate from the pre-market digest in slack_digest.py because those
helpers have different call signatures and this module is imported lazily
from api.indicators.swing.pipeline.postmarket to keep postmarket test
fixtures mockable.

Both helpers are sync wrappers around `send_message` (which is async) —
called from sync pipeline code via `asyncio.run`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from api.integrations.slack import send_message

logger = logging.getLogger(__name__)


def post_postmarket_digest(summary: dict[str, Any]) -> None:
    """Post the post-market digest to the swing Slack channel.

    `summary` keys: active_ideas, stage_transitions, exhaustion_warnings, stop_violations.

    Must be called from sync context (uses asyncio.run internally).
    """
    lines = [
        ":closed_book: *Swing Post-Market Digest*",
        f"Active ideas processed: {summary.get('active_ideas', 0)}",
    ]
    if summary.get("stage_transitions"):
        lines.append(f":arrows_counterclockwise: Stage transitions: {summary['stage_transitions']}")
    if summary.get("exhaustion_warnings"):
        lines.append(f":warning: Exhaustion warnings: {summary['exhaustion_warnings']}")
    if summary.get("stop_violations"):
        lines.append(f":octagonal_sign: Stop violations (invalidated): {summary['stop_violations']}")
    lines.append(":mag: Deep analysis kicking off at 2:30pm PT on user's Mac")
    text = "\n".join(lines)

    try:
        asyncio.run(send_message(text, channel_type="swing-trades"))
    except Exception as e:
        logger.warning("Failed to post postmarket digest to Slack: %s", e)


def post_weekend_refresh_digest(result) -> None:
    """Post the Sunday universe-refresh digest to the swing Slack channel.

    `result` has attributes: skipped (bool), skip_reason, base_count, final_count.

    Must be called from sync context (uses asyncio.run internally).
    """
    if result.skipped:
        text = f":arrows_counterclockwise: Skipped universe refresh: {result.skip_reason}"
    else:
        text = (f":arrows_counterclockwise: *Backend universe refreshed*\n"
                f"Base: {result.base_count}  →  Final: {result.final_count}")
    try:
        asyncio.run(send_message(text, channel_type="swing-trades"))
    except Exception as e:
        logger.warning("Failed to post weekend-refresh digest to Slack: %s", e)
