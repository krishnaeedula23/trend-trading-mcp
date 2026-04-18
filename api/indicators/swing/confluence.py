"""Confluence scoring for swing setup ranking."""

from __future__ import annotations

from api.indicators.swing.setups import SetupHit
from api.indicators.swing.market_health import MarketHealth


def score_hits(
    hits: list[SetupHit],
    ticker: str,
    ctx: dict,
    market_health: MarketHealth,
) -> list[tuple[SetupHit, int]]:
    """Compute confluence scores for all hits on a single ticker.

    Returns list of (hit, confluence_score) tuples in the same order as input.
    """
    multi_setup_bonus = 2 if len(hits) >= 2 else 0
    rs_bonus = 1 if ctx.get("rs_10d", 0) > 0.05 else 0
    market_bonus = 1 if market_health.green_light else 0
    theme_bonus = 1 if ticker in ctx.get("theme_leaders", []) else 0

    result = []
    for h in hits:
        volume_bonus = 1 if h.detection_evidence.get("volume_vs_20d_avg", 0) > 1.5 else 0
        score = h.raw_score + multi_setup_bonus + rs_bonus + market_bonus + volume_bonus + theme_bonus
        score = max(1, min(10, score))
        result.append((h, score))

    return result
