"""IV metrics endpoint — IV Rank and IV Percentile from historical VIX data."""

import yfinance as yf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/options", tags=["options"])


class IvMetricsRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol (SPY, SPX, etc.)")


@router.post("/iv-metrics")
async def iv_metrics(req: IvMetricsRequest):
    """
    Compute IV Rank and IV Percentile from 1 year of VIX history.

    VIX = 30-day implied volatility of S&P 500 (SPX).
    SPY IV tracks VIX very closely, so we use VIX for both.

    IV Rank = (Current - 52w Low) / (52w High - 52w Low) × 100
    IV Percentile = (Days where VIX < Current) / Total Days × 100
    """
    try:
        vix = yf.download("^VIX", period="1y", interval="1d", progress=False)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch VIX data: {exc}"
        ) from exc

    if vix.empty or len(vix) < 10:
        raise HTTPException(
            status_code=404, detail="Insufficient VIX historical data"
        )

    # Handle multi-level columns from yfinance (e.g. ('Close', '^VIX'))
    close_col = vix["Close"]
    if hasattr(close_col, "columns"):
        close_col = close_col.iloc[:, 0]
    closes = close_col.dropna()

    if len(closes) < 10:
        raise HTTPException(
            status_code=404, detail="Insufficient VIX close data after cleanup"
        )

    current_iv = float(closes.iloc[-1])
    high_52w = float(closes.max())
    low_52w = float(closes.min())

    # IV Rank: where does current IV sit in the 52-week range?
    iv_range = high_52w - low_52w
    iv_rank = ((current_iv - low_52w) / iv_range * 100) if iv_range > 0 else 50.0

    # IV Percentile: % of days in the past year where IV was LOWER than current
    days_below = int((closes < current_iv).sum())
    total_days = len(closes)
    iv_percentile = (days_below / total_days * 100) if total_days > 0 else 50.0

    return {
        "ticker": req.ticker.upper(),
        "current_iv": round(current_iv, 2),
        "iv_rank": round(iv_rank, 1),
        "iv_percentile": round(iv_percentile, 1),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
    }
