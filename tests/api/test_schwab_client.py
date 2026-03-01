"""Tests for Schwab client convenience wrappers."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def mock_schwab_client():
    """Return a mocked schwab.client.Client."""
    client = MagicMock()
    with patch("api.integrations.schwab.client.get_client", return_value=client):
        yield client


class TestGetMovers:
    def test_returns_json_for_valid_index(self, mock_schwab_client):
        mock_schwab_client.get_movers.return_value = MagicMock(
            status_code=200,
            json=lambda: {"screener": [{"symbol": "AAPL", "totalVolume": 1_000_000}]},
        )
        mock_schwab_client.get_movers.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_movers

        result = get_movers("$SPX")
        assert result["screener"][0]["symbol"] == "AAPL"
        mock_schwab_client.get_movers.assert_called_once()

    def test_raises_on_bad_status(self, mock_schwab_client):
        from requests.exceptions import HTTPError

        mock_schwab_client.get_movers.return_value = MagicMock()
        mock_schwab_client.get_movers.return_value.raise_for_status.side_effect = HTTPError("502")

        from api.integrations.schwab.client import get_movers

        with pytest.raises(HTTPError):
            get_movers("$SPX")


class TestGetQuotes:
    def test_returns_quotes_for_multiple_symbols(self, mock_schwab_client):
        mock_schwab_client.get_quotes.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "AAPL": {"quote": {"lastPrice": 195.0}},
                "MSFT": {"quote": {"lastPrice": 420.0}},
            },
        )
        mock_schwab_client.get_quotes.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_quotes

        result = get_quotes(["AAPL", "MSFT"])
        assert "AAPL" in result
        assert "MSFT" in result
        mock_schwab_client.get_quotes.assert_called_once()

    def test_single_symbol_as_list(self, mock_schwab_client):
        mock_schwab_client.get_quotes.return_value = MagicMock(
            status_code=200,
            json=lambda: {"SPY": {"quote": {"lastPrice": 500.0}}},
        )
        mock_schwab_client.get_quotes.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_quotes

        result = get_quotes(["SPY"])
        assert "SPY" in result

    def test_raises_on_bad_status(self, mock_schwab_client):
        from requests.exceptions import HTTPError

        mock_schwab_client.get_quotes.return_value = MagicMock()
        mock_schwab_client.get_quotes.return_value.raise_for_status.side_effect = HTTPError("502")

        from api.integrations.schwab.client import get_quotes

        with pytest.raises(HTTPError):
            get_quotes(["AAPL"])


class TestGetInstruments:
    def test_symbol_search(self, mock_schwab_client):
        mock_schwab_client.get_instruments.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "instruments": [
                    {"symbol": "AAPL", "description": "Apple Inc", "exchange": "NASDAQ"},
                ]
            },
        )
        mock_schwab_client.get_instruments.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_instruments

        result = get_instruments("AAPL", projection="symbol_search")
        assert result["instruments"][0]["symbol"] == "AAPL"

    def test_description_search(self, mock_schwab_client):
        mock_schwab_client.get_instruments.return_value = MagicMock(
            status_code=200,
            json=lambda: {"instruments": [{"symbol": "AAPL", "description": "Apple Inc"}]},
        )
        mock_schwab_client.get_instruments.return_value.raise_for_status = MagicMock()

        from api.integrations.schwab.client import get_instruments

        result = get_instruments("Apple", projection="description_search")
        assert len(result["instruments"]) > 0

    def test_raises_on_bad_status(self, mock_schwab_client):
        from requests.exceptions import HTTPError

        mock_schwab_client.get_instruments.return_value = MagicMock()
        mock_schwab_client.get_instruments.return_value.raise_for_status.side_effect = HTTPError("502")

        from api.integrations.schwab.client import get_instruments

        with pytest.raises(HTTPError):
            get_instruments("AAPL")
