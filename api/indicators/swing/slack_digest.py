"""Pre-market Slack digest formatter for swing trading setups."""

from __future__ import annotations

from api.indicators.swing.setups import SetupHit
from api.indicators.swing.market_health import MarketHealth
from api.integrations.slack import send_message

_EMPTY = "🔴 Swing Pre-market — no setups today"


def format_premarket_digest(
    hits_with_scores: list[tuple[SetupHit, int]],
    transitions: list[dict],
    invalidations: list[dict],
    market_health: MarketHealth,
    universe_source: str,
    universe_size: int,
    universe_age_days: int,
) -> str:
    """Format the pre-market swing digest as a Slack message string."""
    no_hits = len(hits_with_scores) == 0
    no_transitions = len(transitions) == 0
    no_invalidations = len(invalidations) == 0
    if no_hits and no_transitions and no_invalidations:
        return _EMPTY

    light = "🟢" if market_health.green_light else "🔴"
    qqq_label = "QQQ green light" if market_health.green_light else "QQQ red light"
    age = f"{universe_age_days}d ago"
    header = (
        f"{light} Swing Pre-market  |  "
        f"Universe: {universe_source} ({universe_size}, {age})  |  {qqq_label}"
    )

    lines = [header, ""]

    # Top setups
    sorted_hits = sorted(hits_with_scores, key=lambda t: t[1], reverse=True)
    top = sorted_hits[:10]
    lines.append(f"Top setups ({len(top)}):")
    for rank, (hit, score) in enumerate(top, 1):
        low, high = hit.entry_zone
        line = (
            f"{rank}. {hit.ticker}  {hit.setup_kell}  {score}/10"
            f"  entry {low:.0f}-{high:.0f}  stop {hit.stop_price:.0f}"
        )
        if hit.first_target is not None:
            if hit.second_target is not None:
                line += f"  targets {hit.first_target:.0f}/{hit.second_target:.0f}"
                close = (low + high) / 2
                denom = close - hit.stop_price
                if denom > 0:
                    rr = (hit.first_target - close) / denom
                    line += f"  R:R {rr:.1f}"
            else:
                line += f"  target {hit.first_target:.0f}"
                close = (low + high) / 2
                denom = close - hit.stop_price
                if denom > 0:
                    rr = (hit.first_target - close) / denom
                    line += f"  R:R {rr:.1f}"
        lines.append(line)

    # Stage transitions (omit section entirely if empty)
    if transitions:
        lines.append("")
        lines.append(f"Stage transitions today ({len(transitions)}):")
        for t in transitions:
            lines.append(f"• {t['ticker']}: {t['from_stage']} → {t['to_stage']}")

    # Invalidations (omit section entirely if empty)
    if invalidations:
        lines.append("")
        lines.append(f"Invalidations ({len(invalidations)}):")
        for inv in invalidations:
            lines.append(f"• {inv['ticker']}: {inv['reason']}")

    lines.append("")
    lines.append("⏳ Analysis pending — Mac will pick up at 6:30am PT")

    return "\n".join(lines)


async def post_premarket_digest(
    hits_with_scores: list[tuple[SetupHit, int]],
    transitions: list[dict],
    invalidations: list[dict],
    market_health: MarketHealth,
    universe_source: str,
    universe_size: int,
    universe_age_days: int,
) -> bool:
    """Format and post the pre-market digest to Slack.

    Always posts — even the empty-digest placeholder — so pipeline silence
    is visible in the channel (easier to notice if the cron didn't run).

    Returns True on success or when Slack is not configured.
    """
    text = format_premarket_digest(
        hits_with_scores, transitions, invalidations,
        market_health, universe_source, universe_size, universe_age_days,
    )
    return await send_message(text, channel_type="swing-trades")
