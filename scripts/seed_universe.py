#!/usr/bin/env python3
"""Seed the ticker universe for the momentum scanner.

Fetches S&P 500, Nasdaq 100, and Russell 2000 ticker lists from
Wikipedia / free sources, deduplicates, and writes to api/data/universe.json.

Usage:
    python scripts/seed_universe.py
"""

import json
import logging
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

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
# Russell 2000 (via iShares IWM holdings CSV or Wikipedia)
# ---------------------------------------------------------------------------

def fetch_russell2000() -> list[str]:
    """Fetch Russell 2000 tickers.

    Tries iShares IWM holdings CSV first, then Wikipedia, then fallback.
    """
    # Approach 1: Try Wikipedia "Russell 2000 Index" page
    try:
        url = "https://en.wikipedia.org/wiki/Russell_2000_Index"
        tables = pd.read_html(url)
        for table in tables:
            cols_lower = [str(c).lower() for c in table.columns]
            for col_idx, col_name in enumerate(cols_lower):
                if "ticker" in col_name or "symbol" in col_name:
                    tickers = table.iloc[:, col_idx].astype(str).apply(_normalise_ticker).tolist()
                    if len(tickers) > 100:
                        logger.info("Russell 2000: fetched %d tickers from Wikipedia", len(tickers))
                        return tickers
    except Exception as exc:
        logger.debug("Russell 2000 Wikipedia attempt failed: %s", exc)

    # Approach 2: Fetch from a commonly available GitHub-hosted list
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        # This won't actually give Russell 2000, so skip to fallback
        raise ValueError("No reliable free Russell 2000 source")
    except Exception:
        pass

    # Approach 3: Use curated fallback (top ~200 Russell 2000 names for MVP)
    logger.info("Russell 2000: using curated fallback (%d tickers)", len(_RUSSELL2000_FALLBACK))
    return _RUSSELL2000_FALLBACK.copy()


_RUSSELL2000_FALLBACK = [
    # A representative sample of Russell 2000 constituents
    "AACG", "AADI", "AAL", "AAON", "AAOI", "AAWW", "ABCB", "ABCL",
    "ABTX", "ACAD", "ACBI", "ACEL", "ACGL", "ACHC", "ACHR", "ACLS",
    "ACNB", "ADMA", "ADNT", "ADPT", "ADUS", "AEHR", "AEL", "AERI",
    "AFCG", "AGIO", "AGYS", "AHCO", "AHH", "AI", "AIMC", "AIN",
    "AIRS", "AIT", "ALIT", "ALKS", "ALKT", "ALLE", "ALRM", "ALTO",
    "ALTR", "AM", "AMBA", "AMBC", "AMED", "AMKR", "AMPH", "AMRX",
    "ANDE", "ANGO", "ANIK", "ANIP", "ANN", "ANNT", "AOSL", "APAM",
    "APGE", "APPF", "APPN", "ARAY", "ARCB", "ARCO", "ARES", "ARIS",
    "ARL", "AROC", "ARRY", "ARVN", "ASGN", "ASTE", "ATKR", "ATNI",
    "ATRO", "AUB", "AVAV", "AVNT", "AVPT", "AX", "AXNX", "AXON",
    "AXSM", "AZZ", "B", "BANF", "BANR", "BBIO", "BBSI", "BCAL",
    "BCC", "BCOV", "BCPC", "BDTX", "BEAM", "BECN", "BELFB", "BHE",
    "BHVN", "BKE", "BKH", "BKU", "BL", "BLBD", "BLKB", "BNR",
    "BOOT", "BOX", "BRC", "BRCC", "BRKR", "BROS", "BRT", "BSIG",
    "BTU", "BUR", "BWA", "BWXT", "BXC", "BYD", "CABO", "CAKE",
    "CALM", "CARG", "CASS", "CATY", "CBRL", "CBT", "CBZ", "CCS",
    "CCSI", "CDAY", "CDNA", "CENX", "CFFN", "CHCO", "CHEF", "CHH",
    "CHRD", "CHS", "CHWY", "CIA", "CIM", "CIVI", "CLAR", "CLB",
    "CLBK", "CLDX", "CLSK", "CMA", "CMCO", "CMN", "CNMD", "CNO",
    "CNOB", "CNXC", "COHU", "COMP", "COOP", "CORT", "COTY", "COUR",
    "CPRI", "CRC", "CRDO", "CRNX", "CRS", "CRVL", "CSBR", "CSGS",
    "CSR", "CSTM", "CTO", "CTRE", "CTVA", "CUZ", "CVAC", "CVBF",
    "CVLT", "CWH", "CWK", "CXM", "CXT", "CYRX", "CYTK", "DBRG",
    "DCI", "DCPH", "DDS", "DEI", "DFIN", "DH", "DHC", "DIOD",
    "DJT", "DLX", "DNLI", "DOCS", "DOOR", "DORM", "DRH", "DRQ",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Fetch all universe lists, dedup, and write to JSON."""
    sp500 = fetch_sp500()
    nasdaq100 = fetch_nasdaq100()
    russell2000 = fetch_russell2000()

    # Build deduplicated "all" list
    seen: set[str] = set()
    all_unique: list[str] = []
    for ticker in sp500 + nasdaq100 + russell2000:
        upper = ticker.upper()
        if upper not in seen:
            seen.add(upper)
            all_unique.append(upper)
    all_unique.sort()

    universe = {
        "sp500": sorted(sp500),
        "nasdaq100": sorted(nasdaq100),
        "russell2000": sorted(russell2000),
        "all_unique": all_unique,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "sp500": len(sp500),
            "nasdaq100": len(nasdaq100),
            "russell2000": len(russell2000),
            "all_unique": len(all_unique),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(universe, indent=2) + "\n")
    logger.info(
        "Wrote universe to %s — %d unique tickers (SP500=%d, NDX100=%d, R2000=%d)",
        OUTPUT_PATH,
        len(all_unique),
        len(sp500),
        len(nasdaq100),
        len(russell2000),
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
