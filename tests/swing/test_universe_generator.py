# tests/swing/test_universe_generator.py
from unittest.mock import patch

from api.indicators.swing.universe.generator import generate_backend_universe


@patch("api.indicators.swing.universe.generator._fetch_bars_bulk")
@patch("api.indicators.swing.universe.generator._fetch_fundamentals")
def test_generator_returns_passers(mock_funds, mock_bars):
    import pandas as pd
    dates = pd.date_range("2025-10-01", periods=220, freq="B")
    mock_bars.side_effect = lambda tickers: {
        "AAPL": pd.DataFrame({"date": dates, "close": [150.0 + i * 0.1 for i in range(220)], "volume": 10_000_000}),
        "PENNY": pd.DataFrame({"date": dates, "close": [3.0] * 220, "volume": 1000}),
        "QQQ":   pd.DataFrame({"date": dates, "close": [400.0 + i * 0.02 for i in range(220)], "volume": 5_000_000}),
    }
    mock_funds.side_effect = lambda t: {
        "AAPL": {"quarterly_revenue_yoy": [0.45, 0.38, 0.30]},
        "PENNY": {"quarterly_revenue_yoy": [0.05, 0.04]},
    }[t]

    result = generate_backend_universe(tickers=["AAPL", "PENNY"])

    assert "AAPL" in result["passers"]
    assert "PENNY" not in result["passers"]
    assert result["passers"]["AAPL"]["fundamentals"] == {"quarterly_revenue_yoy": [0.45, 0.38, 0.30]}
