#!/usr/bin/env python3
"""Seed the ticker universe for the momentum scanner and market monitor.

Fetches a comprehensive list of all US exchange-listed equities from SEC EDGAR,
plus index-specific lists (S&P 500, Nasdaq 100) from Wikipedia. The combined
universe covers ~8,000+ tickers — the market monitor's refresh-universe endpoint
uses Schwab fundamentals to filter down to ~2,500 stocks with $1B+ market cap.

Usage:
    python scripts/seed_universe.py
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

# Regex to identify common-stock tickers (1-5 uppercase letters, no special suffixes)
_COMMON_STOCK_RE = re.compile(r"^[A-Z]{1,5}$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "api" / "data" / "universe.json"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
}


def _fetch_html(url: str) -> str:
    """Fetch HTML content with a browser user-agent to avoid 403."""
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _normalise_ticker(ticker: str) -> str:
    """Replace dots with dashes for yfinance compatibility (e.g. BRK.B -> BRK-B)."""
    return ticker.strip().replace(".", "-")


# ---------------------------------------------------------------------------
# S&P 500
# ---------------------------------------------------------------------------

def fetch_sp500() -> list[str]:
    """Fetch S&P 500 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        html = _fetch_html(url)
        tables = pd.read_html(StringIO(html))
        df = tables[0]
        tickers = df.iloc[:, 0].astype(str).apply(_normalise_ticker).tolist()
        logger.info("S&P 500: fetched %d tickers from Wikipedia", len(tickers))
        return tickers
    except Exception as exc:
        logger.warning("S&P 500 Wikipedia fetch failed: %s — using fallback", exc)
        return _SP500_FALLBACK.copy()


_SP500_FALLBACK = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B",
    "UNH", "JNJ", "V", "JPM", "XOM", "PG", "MA", "HD", "CVX", "ABBV",
    "MRK", "LLY", "PEP", "KO", "AVGO", "COST", "WMT", "MCD", "CSCO",
    "TMO", "ACN", "ABT", "DHR", "NEE", "LIN", "PM", "TXN", "BMY",
    "UNP", "RTX", "AMGN", "HON", "LOW", "COP", "ORCL", "QCOM", "INTC",
    "BA", "CAT", "GS", "AMD",
]


# ---------------------------------------------------------------------------
# Nasdaq 100
# ---------------------------------------------------------------------------

def fetch_nasdaq100() -> list[str]:
    """Fetch Nasdaq 100 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        html = _fetch_html(url)
        tables = pd.read_html(StringIO(html))
        # The main table usually has "Ticker" or "Symbol" in a column header
        for table in tables:
            cols_lower = [str(c).lower() for c in table.columns]
            for col_idx, col_name in enumerate(cols_lower):
                if "ticker" in col_name or "symbol" in col_name:
                    tickers = table.iloc[:, col_idx].astype(str).apply(_normalise_ticker).tolist()
                    logger.info("Nasdaq 100: fetched %d tickers from Wikipedia", len(tickers))
                    return tickers
        # Fallback: first column of second table is usually tickers
        df = tables[4] if len(tables) > 4 else tables[0]
        tickers = df.iloc[:, 1].astype(str).apply(_normalise_ticker).tolist()
        logger.info("Nasdaq 100: fetched %d tickers (table heuristic)", len(tickers))
        return tickers
    except Exception as exc:
        logger.warning("Nasdaq 100 Wikipedia fetch failed: %s — using fallback", exc)
        return _NASDAQ100_FALLBACK.copy()


_NASDAQ100_FALLBACK = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "TSLA", "GOOGL", "GOOG",
    "AVGO", "COST", "PEP", "CSCO", "AMD", "ADBE", "NFLX", "TMUS",
    "CMCSA", "INTC", "INTU", "TXN", "QCOM", "AMGN", "HON", "AMAT",
    "SBUX", "ISRG", "BKNG", "MDLZ", "ADP", "LRCX", "ADI", "REGN",
    "VRTX", "SNPS", "PANW", "KLAC", "MU", "CDNS", "PYPL", "MELI",
    "ABNB", "GILD", "MAR", "CSX", "ORLY", "MRVL", "NXPI", "CTAS",
    "FTNT", "PCAR",
]


# ---------------------------------------------------------------------------
# SEC EDGAR — comprehensive all-exchange-listed equities
# ---------------------------------------------------------------------------

def fetch_sec_edgar() -> list[str]:
    """Fetch all exchange-listed equity tickers from SEC EDGAR.

    Uses the SEC's company_tickers_exchange.json which lists every company
    filing with the SEC along with their exchange (NYSE, Nasdaq, etc.).
    Filters to common-stock tickers only (1-5 uppercase letters, no warrants,
    units, preferred shares, or other special instruments).

    Returns ~8,000+ tickers covering all US-listed equities.
    """
    url = "https://www.sec.gov/files/company_tickers_exchange.json"
    valid_exchanges = {"NYSE", "Nasdaq", "AMEX", "BATS", "CBOE", "NYSEARCA", "NYSEAMERICAN"}

    try:
        # SEC EDGAR requires a real company/email user-agent per their fair-access policy
        edgar_headers = {"User-Agent": "SatyTrading admin@satytrading.com", "Accept": "application/json"}
        resp = requests.get(url, headers=edgar_headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Format: {"fields": ["cik","name","ticker","exchange"], "data": [[cik, name, ticker, exchange], ...]}
        fields = data.get("fields", [])
        rows = data.get("data", [])

        ticker_idx = fields.index("ticker") if "ticker" in fields else 2
        exchange_idx = fields.index("exchange") if "exchange" in fields else 3

        tickers: list[str] = []
        for row in rows:
            raw_ticker = str(row[ticker_idx]).strip().upper()
            exchange = str(row[exchange_idx]).strip()

            # Filter: major US exchanges only, common stock tickers only
            if exchange not in valid_exchanges:
                continue
            ticker = _normalise_ticker(raw_ticker)
            if _COMMON_STOCK_RE.match(ticker):
                tickers.append(ticker)

        tickers = sorted(set(tickers))
        logger.info("SEC EDGAR: fetched %d common-stock tickers from %d total filings", len(tickers), len(rows))
        return tickers

    except Exception as exc:
        logger.warning("SEC EDGAR fetch failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# NASDAQ exchange-listed stocks (supplementary)
# ---------------------------------------------------------------------------

def fetch_nasdaq_listed() -> list[str]:
    """Fetch all NASDAQ-listed tickers from NASDAQ's FTP-style endpoint.

    This catches tickers that may not appear in the SEC EDGAR file yet
    (e.g. recently listed IPOs).
    """
    url = "https://api.nasdaq.com/api/screener/stocks?tableType=earnings&limit=10000&offset=0"
    try:
        resp = requests.get(url, headers={**_HEADERS, "Accept": "application/json"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("data", {}).get("table", {}).get("rows", [])
        tickers = []
        for row in rows:
            raw = str(row.get("symbol", "")).strip().upper()
            ticker = _normalise_ticker(raw)
            if _COMMON_STOCK_RE.match(ticker):
                tickers.append(ticker)
        tickers = sorted(set(tickers))
        logger.info("NASDAQ screener: fetched %d common-stock tickers", len(tickers))
        return tickers
    except Exception as exc:
        logger.warning("NASDAQ screener fetch failed: %s — skipping", exc)
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Fetch all universe lists, dedup, and write to JSON."""
    sp500 = fetch_sp500()
    nasdaq100 = fetch_nasdaq100()
    sec_edgar = fetch_sec_edgar()
    nasdaq_listed = fetch_nasdaq_listed()

    # Build deduplicated "all" list — SEC EDGAR is the broadest source
    seen: set[str] = set()
    all_unique: list[str] = []
    for ticker in sec_edgar + nasdaq_listed + sp500 + nasdaq100:
        upper = ticker.upper()
        if upper not in seen:
            seen.add(upper)
            all_unique.append(upper)
    all_unique.sort()

    universe = {
        "sp500": sorted(sp500),
        "nasdaq100": sorted(nasdaq100),
        "sec_edgar": sorted(sec_edgar),
        "all_unique": all_unique,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "sp500": len(sp500),
            "nasdaq100": len(nasdaq100),
            "sec_edgar": len(sec_edgar),
            "nasdaq_listed": len(nasdaq_listed),
            "all_unique": len(all_unique),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(universe, indent=2) + "\n")
    logger.info(
        "Wrote universe to %s — %d unique tickers (SP500=%d, NDX100=%d, SEC_EDGAR=%d, NASDAQ=%d)",
        OUTPUT_PATH,
        len(all_unique),
        len(sp500),
        len(nasdaq100),
        len(sec_edgar),
        len(nasdaq_listed),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        sys.exit(1)
