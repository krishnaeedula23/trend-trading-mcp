"""Schwab market-data endpoints."""

import os

from fastapi import APIRouter, HTTPException, Query

import schwab.auth
from api.integrations.schwab import client as schwab_client
from api.integrations.schwab.token_manager import TOKEN_PATH, token_exists

router = APIRouter(prefix="/api/schwab", tags=["schwab"])

# Holds the auth_context between /auth/url and /auth/callback calls
_pending_auth_context = None


@router.get("/quote")
async def get_quote(ticker: str = Query(..., description="Ticker symbol, e.g. AAPL")):
    """Return a real-time quote for a single ticker."""
    _require_token()
    try:
        return schwab_client.get_quote(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc


@router.get("/options-chain")
async def get_options_chain(
    ticker: str = Query(..., description="Ticker symbol"),
    strike_count: int = Query(10, ge=1, le=50),
):
    """Return the full options chain for a ticker."""
    _require_token()
    try:
        return schwab_client.get_option_chain(ticker, strike_count=strike_count)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc


@router.get("/price-history")
async def get_price_history(
    ticker: str = Query(..., description="Ticker symbol"),
    frequency: str = Query("5m", description="Bar frequency: 1m | 5m | 10m | 15m | 30m | 1d | 1w"),
):
    """Return OHLCV price history from Schwab."""
    _require_token()
    try:
        return schwab_client.get_price_history(ticker, frequency_type=frequency)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schwab API error: {exc}") from exc


@router.get("/auth/url")
async def get_auth_url():
    """
    Step 1 of OAuth: get the Schwab authorization URL.

    Open this URL in a browser, log in, approve access.
    Schwab will redirect to your callback URL with a 'code' parameter.
    Copy the ENTIRE redirect URL and pass it to POST /api/schwab/auth/callback.
    """
    client_id = os.getenv("SCHWAB_CLIENT_ID", "")
    callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1")
    if not client_id:
        raise HTTPException(status_code=500, detail="SCHWAB_CLIENT_ID not configured")

    global _pending_auth_context
    _pending_auth_context = schwab.auth.get_auth_context(client_id, callback_url)
    return {
        "step": 1,
        "auth_url": _pending_auth_context.authorization_url,
        "callback_url": _pending_auth_context.callback_url,
        "state": _pending_auth_context.state,
        "instructions": (
            "1. Open auth_url in your browser and log in to Schwab. "
            "2. After approving, copy the ENTIRE redirect URL from your browser. "
            "3. POST that URL to /api/schwab/auth/callback as the 'received_url' body field."
        ),
    }


@router.post("/auth/callback")
async def auth_callback(received_url: str):
    """
    Step 2 of OAuth: exchange the redirect URL for tokens.

    Paste the ENTIRE URL your browser was redirected to after Schwab login.
    schwab-py exchanges the code for tokens and saves them to SCHWAB_TOKEN_FILE.
    """
    global _pending_auth_context
    client_id = os.getenv("SCHWAB_CLIENT_ID", "")
    app_secret = os.getenv("SCHWAB_CLIENT_SECRET", "")

    if not client_id or not app_secret:
        raise HTTPException(status_code=500, detail="SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET not configured")
    if _pending_auth_context is None:
        raise HTTPException(status_code=400, detail="No pending auth session. Call GET /api/schwab/auth/url first.")

    auth_context = _pending_auth_context

    def write_token(token):
        import json
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(json.dumps(token))

    try:
        schwab.auth.client_from_received_url(
            api_key=client_id,
            app_secret=app_secret,
            auth_context=auth_context,
            received_url=received_url,
            token_write_func=write_token,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {exc}") from exc

    # Clear pending context and reset client singleton
    _pending_auth_context = None
    schwab_client.reset_client()
    return {"status": "tokens saved", "token_file": str(TOKEN_PATH)}


@router.get("/auth/status")
async def auth_status():
    """Check whether a valid token file exists."""
    return {
        "token_file": str(TOKEN_PATH),
        "token_exists": token_exists(),
        "ready": token_exists(),
    }


def _require_token():
    if not token_exists():
        raise HTTPException(
            status_code=401,
            detail=(
                "No Schwab token found. Complete OAuth: "
                "GET /api/schwab/auth/url → browser → POST /api/schwab/auth/callback"
            ),
        )
