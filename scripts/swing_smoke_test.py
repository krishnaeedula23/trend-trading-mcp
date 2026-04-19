"""Smoke-test helper for the swing pre-market pipeline.

Runs run_premarket_detection() against the real Supabase project and real yfinance
bars. Prints the result dict and exits non-zero if the pipeline itself raises.

Requires these env vars (set in .env or exported in the shell):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY

Optional:
  SLACK_BOT_TOKEN + SLACK_CHANNEL_SWING_TRADES — posts digest. Omitted → digest skipped.
  FINNHUB_API_KEY — earnings calendar fallback for post_eps_flag detector.

Usage:
  .venv/bin/python scripts/swing_smoke_test.py

Assumes swing_universe already has rows. If empty, this script prints a hint
and exits without running the pipeline.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("❌ SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.", file=sys.stderr)
        return 1

    from supabase import create_client
    sb = create_client(url, key)

    active = sb.table("swing_universe").select("ticker").is_("removed_at", None).execute().data or []
    if not active:
        print("❌ swing_universe has 0 active rows. Seed the universe first (see README).")
        return 1
    print(f"Universe: {len(active)} active tickers ({', '.join(r['ticker'] for r in active[:5])}{'...' if len(active) > 5 else ''})")

    from api.indicators.swing.pipeline import run_premarket_detection
    print("Running pipeline (may take 30-60s for yfinance bar fetch)...")
    result = run_premarket_detection(sb)

    print("\nResult:")
    for key_ in ("new_ideas", "transitions", "invalidations", "errors", "universe_source", "universe_size"):
        print(f"  {key_}: {result.get(key_)}")
    mh = result.get("market_health") or {}
    if mh:
        print(f"  market_health.index_cycle_stage: {mh.get('index_cycle_stage')}")
        print(f"  market_health.green_light: {mh.get('green_light')}")

    if result.get("errors", 0) > 0:
        print(f"\n⚠️  {result['errors']} errors logged during run — check stderr.")
        return 2

    print("\n✅ Pipeline ran without errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
