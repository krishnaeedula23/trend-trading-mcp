#!/usr/bin/env python3
"""End-to-end smoke test for the morning screener.

Runs against a real Supabase + yfinance — does NOT mock anything. Use sparingly.

Usage:
    venv/bin/python scripts/screener_smoke_test.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

# Ensure scans are registered
import api.indicators.screener.scans.coiled  # noqa: F401
from api.indicators.screener.bars import fetch_daily_bars_bulk
from api.indicators.screener.runner import run_screener
from supabase import create_client


SAMPLE_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "AMD", "MXL", "PLTR", "META", "AVGO", "COST"]


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", file=sys.stderr)
        return 1

    sb = create_client(url, key)

    print(f"Fetching bars for {len(SAMPLE_TICKERS)} tickers...")
    bars = fetch_daily_bars_bulk(SAMPLE_TICKERS, period="6mo")
    print(f"  Got bars for {len(bars)} tickers.")

    print("Running screener...")
    response = run_screener(
        sb=sb,
        mode="swing",
        bars_by_ticker=bars,
        today=date.today(),
    )

    print(f"\nRun {response.run_id} — {response.duration_seconds}s")
    print(f"  Universe size: {response.universe_size}")
    print(f"  Scans run: {response.scan_count}")
    print(f"  Hits: {response.hit_count}")
    for tr in response.tickers:
        print(f"  {tr.ticker:6s}  Ext={tr.overlay.extension:+6.2f}  "
              f"ATR%={tr.overlay.atr_pct*100:5.2f}  "
              f"scans={tr.scans_hit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
