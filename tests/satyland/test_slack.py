from api.integrations.slack import (
    format_setup_alert,
    format_morning_brief,
    format_journal_prompt,
    format_simple_alert,
)


class TestSlackFormatters:
    """Test Slack message formatting functions."""

    def test_format_setup_alert(self):
        grade_result = {
            "setup_type": "flag_into_ribbon",
            "direction": "bullish",
            "grade": "A",
            "probability": 0.65,
            "probability_source": "estimated",
            "required_flags": [
                {"name": "ribbon_stacked", "passed": True, "reason": "Bullish"},
                {"name": "atr_room", "passed": True, "reason": "50% consumed"},
            ],
            "bonus_flags": [
                {"name": "phase_firing", "passed": True, "reason": "Green"},
                {"name": "mtf_aligned", "passed": False, "reason": "Conflict"},
            ],
        }
        text = format_setup_alert(grade_result, "SPY", "3m", 562.40)
        assert "FLAG INTO RIBBON" in text
        assert "SPY" in text
        assert "Long" in text
        assert "A" in text
        assert "65%" in text
        assert "take" in text.lower()

    def test_format_setup_alert_bearish(self):
        grade_result = {
            "setup_type": "golden_gate",
            "direction": "bearish",
            "grade": "A+",
            "probability": 0.902,
            "probability_source": "backtested",
            "required_flags": [],
            "bonus_flags": [],
        }
        text = format_setup_alert(grade_result, "SPY", "10m", 555.0)
        assert "Short" in text
        assert "🔴" in text
        assert "90%" in text

    def test_format_morning_brief(self):
        text = format_morning_brief({
            "ticker": "SPY",
            "structural_bias": "Bullish",
            "vix_reading": 15.2,
        })
        assert "Morning Brief" in text
        assert "SPY" in text
        assert "Bullish" in text

    def test_format_journal_prompt(self):
        text = format_journal_prompt({
            "total_trades": 3,
            "total_pnl": 420,
            "total_r": 2.1,
        })
        assert "Journal Time" in text
        assert "3 trades" in text
        assert "focused" in text

    def test_format_simple_alert(self):
        text = format_simple_alert("Trend Time", "Ribbon establishing direction.")
        assert "Trend Time" in text
        assert "Ribbon" in text
