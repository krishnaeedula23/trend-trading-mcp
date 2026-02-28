"""Options analytics endpoints."""

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.integrations.schwab.client import get_option_chain

router = APIRouter(prefix="/api/options", tags=["options"])


class TickerRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")
    strike_count: int = Field(10, ge=1, le=50)


class GEXRequest(BaseModel):
    ticker: str = Field(..., description="Ticker symbol")
    strike_count: int = Field(20, ge=1, le=50)


def _find_atm_options(chain: dict, spot: float) -> dict:
    """Extract the nearest ATM call and put from a Schwab options chain response."""
    calls = chain.get("callExpDateMap", {})
    puts = chain.get("putExpDateMap", {})

    best_call = None
    best_put = None
    best_diff = float("inf")

    # Take the nearest expiration (first key)
    for exp_key in calls:
        for strike_str, options in calls[exp_key].items():
            diff = abs(float(strike_str) - spot)
            if diff < best_diff:
                best_diff = diff
                best_call = options[0] if options else None
                # Find matching put
                for put_exp_key in puts:
                    if put_exp_key == exp_key and strike_str in puts[put_exp_key]:
                        best_put = puts[put_exp_key][strike_str][0]
        break  # Only first expiration

    return {"call": best_call, "put": best_put}


@router.post("/atm-straddle")
async def atm_straddle(req: TickerRequest):
    """
    Compute the ATM straddle price and expected move.

    Expected Move = Straddle Price × 0.85
    """
    try:
        chain = get_option_chain(req.ticker, strike_count=req.strike_count)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc

    underlying = chain.get("underlying", {})
    spot = float(underlying.get("last", underlying.get("mark", 0)))
    if spot == 0:
        raise HTTPException(status_code=400, detail="Could not determine spot price from chain")

    atm = _find_atm_options(chain, spot)
    call = atm["call"]
    put = atm["put"]

    if not call or not put:
        raise HTTPException(status_code=404, detail="ATM options not found in chain")

    call_price = float(call.get("mark", call.get("last", 0)))
    put_price = float(put.get("mark", put.get("last", 0)))
    straddle_price = call_price + put_price
    expected_move = round(straddle_price * 0.85, 2)
    expected_move_pct = round(expected_move / spot * 100, 2) if spot > 0 else 0.0

    # Extract per-contract implied volatility (Schwab field: "volatility" or "impliedVolatility")
    call_iv = float(call.get("volatility", call.get("impliedVolatility", 0)) or 0)
    put_iv = float(put.get("volatility", put.get("impliedVolatility", 0)) or 0)
    atm_iv = (call_iv + put_iv) / 2 if (call_iv and put_iv) else call_iv or put_iv

    return {
        "ticker": req.ticker.upper(),
        "spot": spot,
        "atm_strike": float(call.get("strikePrice", 0)),
        "call_price": round(call_price, 2),
        "put_price": round(put_price, 2),
        "straddle_price": round(straddle_price, 2),
        "expected_move": expected_move,
        "expected_move_pct": expected_move_pct,
        "expiration": call.get("expirationDate", ""),
        "days_to_expiry": call.get("daysToExpiration", 0),
        "call_iv": round(call_iv, 4),
        "put_iv": round(put_iv, 4),
        "atm_iv": round(atm_iv, 4),
    }


@router.post("/gamma-exposure")
async def gamma_exposure(req: GEXRequest):
    """
    Compute net Gamma Exposure (GEX) across all strikes.

    GEX per strike = Net OI × Gamma × Spot² × 100 × contract_size
    Positive GEX = dealers are long gamma (stabilizing)
    Negative GEX = dealers are short gamma (amplifying)
    """
    try:
        chain = get_option_chain(req.ticker, strike_count=req.strike_count)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc

    underlying = chain.get("underlying", {})
    spot = float(underlying.get("last", underlying.get("mark", 0)))

    calls_map = chain.get("callExpDateMap", {})
    puts_map = chain.get("putExpDateMap", {})

    gex_by_strike: dict[float, float] = {}

    def _accumulate(options_map: dict, sign: float) -> None:
        for exp_key in options_map:
            for strike_str, options in options_map[exp_key].items():
                strike = float(strike_str)
                for opt in options:
                    gamma = float(opt.get("gamma", 0) or 0)
                    oi = float(opt.get("openInterest", 0) or 0)
                    gex = sign * oi * gamma * spot**2 * 0.01  # ÷100 shares, ×100 contracts
                    gex_by_strike[strike] = gex_by_strike.get(strike, 0.0) + gex

    _accumulate(calls_map, 1.0)   # Dealers short calls → long gamma
    _accumulate(puts_map, -1.0)   # Dealers short puts → short gamma

    total_gex = sum(gex_by_strike.values())
    sorted_strikes = sorted(gex_by_strike.items())
    # Find zero-gamma level (sign change)
    zero_gamma = None
    for i in range(1, len(sorted_strikes)):
        g_prev = sorted_strikes[i - 1][1]
        g_curr = sorted_strikes[i][1]
        if g_prev * g_curr < 0:
            # Linear interpolation
            s_prev, s_curr = sorted_strikes[i - 1][0], sorted_strikes[i][0]
            zero_gamma = round(s_prev + (s_curr - s_prev) * abs(g_prev) / (abs(g_prev) + abs(g_curr)), 2)
            break

    return {
        "ticker": req.ticker.upper(),
        "spot": spot,
        "total_gex": round(total_gex, 2),
        "total_gex_millions": round(total_gex / 1_000_000, 3),
        "dealer_positioning": "long_gamma" if total_gex > 0 else "short_gamma",
        "zero_gamma_level": zero_gamma,
        "gex_by_strike": {str(s): round(g, 2) for s, g in sorted_strikes},
    }
