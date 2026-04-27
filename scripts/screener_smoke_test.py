#!/usr/bin/env python3
"""End-to-end smoke test for the morning screener.

Runs against real Supabase + yfinance — does NOT mock anything. Use sparingly.

Usage:
    venv/bin/python scripts/screener_smoke_test.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date

# Ensure every scan is registered
import api.indicators.screener.scans  # noqa: F401
from api.indicators.screener.bars import (
    fetch_daily_bars_bulk,
    fetch_hourly_bars_bulk,
)
from api.indicators.screener.runner import run_screener
from supabase import create_client


# Representative tickers across mega-caps, momentum, and broad sectors.
SAMPLE_TICKERS = [
    "NVDA", "AAPL", "MSFT", "TSLA", "AMD", "META", "AVGO", "COST", "GOOGL",
    "MXL", "PLTR", "CRWD", "PANW", "VRT", "SOFI", "MSTR", "COIN",
    "NFLX", "ABNB", "UBER", "LLY", "UNH", "XOM", "WMT", "JPM",
    "QQQ",
]


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", file=sys.stderr)
        return 1

    sb = create_client(url, key)

    print(f"Fetching daily bars for {len(SAMPLE_TICKERS)} tickers...")
    daily = fetch_daily_bars_bulk(SAMPLE_TICKERS, period="1y")
    print(f"  Got daily bars for {len(daily)} tickers.")

    print("Fetching hourly bars (60d)...")
    hourly = fetch_hourly_bars_bulk(SAMPLE_TICKERS, period="60d")
    print(f"  Got hourly bars for {len(hourly)} tickers.")

    print("Running screener...")
    response = run_screener(
        sb=sb,
        mode="swing",
        bars_by_ticker=daily,
        hourly_bars_by_ticker=hourly,
        today=date.today(),
    )

    print()
    print(f"Run {response.run_id} — {response.duration_seconds}s")
    print(f"  Universe size : {response.universe_size}")
    print(f"  Scans run     : {response.scan_count}")
    print(f"  Hits          : {response.hit_count}")
    print(f"  Sectors       : {response.sector_summary}")

    # Per-scan hit counts
    scan_counter: Counter[str] = Counter()
    for t in response.tickers:
        for s in t.scans_hit:
            scan_counter[s] += 1
    print()
    print("Per-scan hit counts:")
    for scan_id, n in sorted(scan_counter.items(), key=lambda kv: -kv[1]):
        print(f"  {scan_id:40s}  {n}")

    print()
    print("Per-ticker results:")
    for tr in sorted(response.tickers, key=lambda t: -t.confluence):
        print(
            f"  {tr.ticker:6s} conf={tr.confluence:>3d} "
            f"ext={tr.overlay.extension:+6.2f} atr%={tr.overlay.atr_pct*100:5.2f} "
            f"phase={tr.overlay.phase_oscillator:+6.1f} "
            f"sec={tr.sector[:12]:<12s} scans={tr.scans_hit}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
