"""Tests for the ticker→sector cache."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sector_returns_yfinance_value(mock_ticker_cls):
    from api.indicators.screener.sectors import get_sector

    inst = MagicMock()
    inst.info = {"sector": "Technology"}
    mock_ticker_cls.return_value = inst
    assert get_sector("NVDA") == "Technology"


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sector_caches_result(mock_ticker_cls):
    """Repeated calls for same ticker should not call yfinance again."""
    from api.indicators.screener.sectors import get_sector, _CACHE

    _CACHE.clear()
    inst = MagicMock()
    inst.info = {"sector": "Healthcare"}
    mock_ticker_cls.return_value = inst

    get_sector("LLY")
    get_sector("LLY")
    get_sector("LLY")
    assert mock_ticker_cls.call_count == 1


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sector_returns_unknown_on_missing(mock_ticker_cls):
    from api.indicators.screener.sectors import get_sector, _CACHE
    _CACHE.clear()
    inst = MagicMock()
    inst.info = {}  # no 'sector' key
    mock_ticker_cls.return_value = inst
    assert get_sector("UNKNOWN") == "Unknown"


@patch("api.indicators.screener.sectors.yf.Ticker", side_effect=Exception("boom"))
def test_get_sector_returns_unknown_on_exception(_):
    from api.indicators.screener.sectors import get_sector, _CACHE
    _CACHE.clear()
    assert get_sector("BAD") == "Unknown"


@patch("api.indicators.screener.sectors.yf.Ticker")
def test_get_sectors_bulk_returns_dict(mock_ticker_cls):
    from api.indicators.screener.sectors import get_sectors_bulk, _CACHE
    _CACHE.clear()

    def make_inst(symbol):
        m = MagicMock()
        m.info = {"sector": "Technology" if symbol == "NVDA" else "Energy"}
        return m

    mock_ticker_cls.side_effect = lambda s: make_inst(s)
    out = get_sectors_bulk(["NVDA", "XOM"])
    assert out == {"NVDA": "Technology", "XOM": "Energy"}
