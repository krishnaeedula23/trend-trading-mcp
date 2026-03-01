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
import schwab.client

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


def get_movers(
    index: str = "$SPX",
    sort_order: str | None = None,
    frequency: int | None = None,
) -> dict[str, Any]:
    """Top movers for a market index (e.g. $SPX, $DJI, $COMPX)."""
    kwargs: dict[str, Any] = {}
    idx_map = {
        "$SPX": schwab.client.Client.Movers.Index.SPX,
        "$DJI": schwab.client.Client.Movers.Index.DJI,
        "$COMPX": schwab.client.Client.Movers.Index.COMPX,
        "$NYSE": schwab.client.Client.Movers.Index.NYSE,
        "$NASDAQ": schwab.client.Client.Movers.Index.NASDAQ,
    }
    idx = idx_map.get(index.upper(), schwab.client.Client.Movers.Index.SPX)

    if sort_order:
        order_map = {
            "volume": schwab.client.Client.Movers.SortOrder.VOLUME,
            "trades": schwab.client.Client.Movers.SortOrder.TRADES,
            "percent_change_up": schwab.client.Client.Movers.SortOrder.PERCENT_CHANGE_UP,
            "percent_change_down": schwab.client.Client.Movers.SortOrder.PERCENT_CHANGE_DOWN,
        }
        mapped_order = order_map.get(sort_order.lower())
        if mapped_order is not None:
            kwargs["sort_order"] = mapped_order
    if frequency is not None:
        freq_map = {
            0: schwab.client.Client.Movers.Frequency.ZERO,
            1: schwab.client.Client.Movers.Frequency.ONE,
            5: schwab.client.Client.Movers.Frequency.FIVE,
            10: schwab.client.Client.Movers.Frequency.TEN,
            30: schwab.client.Client.Movers.Frequency.THIRTY,
            60: schwab.client.Client.Movers.Frequency.SIXTY,
        }
        mapped_freq = freq_map.get(frequency)
        if mapped_freq is not None:
            kwargs["frequency"] = mapped_freq

    resp = get_client().get_movers(idx, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_quotes(symbols: list[str]) -> dict[str, Any]:
    """Batch quotes for multiple symbols."""
    resp = get_client().get_quotes([s.upper() for s in symbols])
    resp.raise_for_status()
    return resp.json()


def get_instruments(query: str, projection: str = "symbol_search") -> dict[str, Any]:
    """Search for instruments by symbol or description."""
    proj_map = {
        "symbol_search": schwab.client.Client.Instrument.Projection.SYMBOL_SEARCH,
        "symbol_regex": schwab.client.Client.Instrument.Projection.SYMBOL_REGEX,
        "description_search": schwab.client.Client.Instrument.Projection.DESCRIPTION_SEARCH,
        "description_regex": schwab.client.Client.Instrument.Projection.DESCRIPTION_REGEX,
        "search": schwab.client.Client.Instrument.Projection.SEARCH,
        "fundamental": schwab.client.Client.Instrument.Projection.FUNDAMENTAL,
    }
    proj = proj_map.get(projection.lower(), schwab.client.Client.Instrument.Projection.SYMBOL_SEARCH)
    resp = get_client().get_instruments(query, proj)
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
