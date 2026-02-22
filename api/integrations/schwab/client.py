"""
Schwab API client via schwab-py.

schwab-py handles OAuth2, token refresh, and the HTTP session.
We expose a singleton that is loaded once from the persisted token file.

First-time setup (run locally, once):
    python scripts/schwab_auth.py
"""

import os
from typing import Any

import schwab.auth

from api.integrations.schwab.token_manager import TOKEN_PATH, token_exists

_client = None  # schwab.client.Client singleton


def _build_client():
    if not token_exists():
        raise RuntimeError(
            "No Schwab token found. Run 'python scripts/schwab_auth.py' locally "
            "to complete the OAuth flow and generate the token file, then deploy it."
        )
    return schwab.auth.client_from_token_file(
        token_path=str(TOKEN_PATH),
        api_key=os.environ["SCHWAB_CLIENT_ID"],
        app_secret=os.environ["SCHWAB_CLIENT_SECRET"],
    )


def get_client():
    """Return the singleton schwab client, building it on first call."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def reset_client():
    """Force client re-initialisation (e.g. after token refresh)."""
    global _client
    _client = None


# ── Convenience wrappers ──────────────────────────────────────────────────────

def get_quote(ticker: str) -> dict[str, Any]:
    resp = get_client().get_quote(ticker.upper())
    resp.raise_for_status()
    return resp.json()


def get_option_chain(ticker: str, strike_count: int = 10) -> dict[str, Any]:
    resp = get_client().get_option_chain(
        ticker.upper(),
        strike_count=strike_count,
        include_underlying_quote=True,
    )
    resp.raise_for_status()
    return resp.json()


def get_price_history(
    ticker: str,
    frequency_type: str = "5m",
) -> dict[str, Any]:
    """
    Fetch recent price history. frequency_type maps to schwab-py helper methods:
      "1m"  → get_price_history_every_minute
      "5m"  → get_price_history_every_five_minutes
      "15m" → get_price_history_every_fifteen_minutes
      "30m" → get_price_history_every_thirty_minutes
      "1d"  → get_price_history_every_day
    """
    method_map = {
        "1m":  "get_price_history_every_minute",
        "5m":  "get_price_history_every_five_minutes",
        "10m": "get_price_history_every_ten_minutes",
        "15m": "get_price_history_every_fifteen_minutes",
        "30m": "get_price_history_every_thirty_minutes",
        "1d":  "get_price_history_every_day",
        "1w":  "get_price_history_every_week",
    }
    method_name = method_map.get(frequency_type, "get_price_history_every_five_minutes")
    method = getattr(get_client(), method_name)
    resp = method(ticker.upper())
    resp.raise_for_status()
    return resp.json()
