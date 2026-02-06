"""
Test Turnover Tracker - Unit tests for turnover tracking service
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from services.turnover_tracker import TurnoverTrackerService


class TestTurnoverTrackerService:
    """Test TurnoverTrackerService class"""

    def setup_method(self):
        self.tracker = TurnoverTrackerService()

    # ===== Helper Method Tests =====

    def test_get_day_data_found(self):
        """Test getting day data when it exists"""
        history = [
            {"date": "2024-01-05", "close": 110, "change_pct": 5.0},
            {"date": "2024-01-04", "close": 108, "change_pct": 3.0},
            {"date": "2024-01-03", "close": 105, "change_pct": 2.0},
            {"date": "2024-01-02", "close": 103, "change_pct": 1.0},
        ]
        trigger_date = date(2024, 1, 1)

        # Get day 1 after trigger (first item in sorted history)
        result = self.tracker._get_day_data(history, trigger_date, 1)
        assert result is not None
        assert result["close"] == 110  # Returns first available after trigger

        # Get day 3 after trigger
        result = self.tracker._get_day_data(history, trigger_date, 3)
        assert result is not None
        assert result["close"] == 105

    def test_get_day_data_not_found(self):
        """Test getting day data when it doesn't exist"""
        history = [
            {"date": "2024-01-02", "close": 103, "change_pct": 1.0},
        ]
        trigger_date = date(2024, 1, 1)

        # Try to get day 5 (doesn't exist)
        result = self.tracker._get_day_data(history, trigger_date, 5)
        assert result is None

    def test_get_day_data_empty_history(self):
        """Test getting day data with empty history"""
        result = self.tracker._get_day_data([], date(2024, 1, 1), 1)
        assert result is None


class TestDateUtils:
    """Test date utility functions"""

    def test_parse_date_valid(self):
        """Test parsing valid date string"""
        from utils.date_utils import parse_date
        result = parse_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_date_invalid(self):
        """Test parsing invalid date string"""
        from utils.date_utils import parse_date
        assert parse_date("invalid") is None
        assert parse_date("2024-13-01") is None
        assert parse_date("") is None

    def test_parse_date_none(self):
        """Test parsing None"""
        from utils.date_utils import parse_date
        assert parse_date(None) is None

    def test_validate_date_str(self):
        """Test date string validation"""
        from utils.date_utils import validate_date_str
        assert validate_date_str("2024-01-15") is True
        assert validate_date_str("invalid") is False
        assert validate_date_str("2024-13-01") is False

    def test_is_trading_day(self):
        """Test trading day detection"""
        from utils.date_utils import is_trading_day

        # Weekday (Monday)
        assert is_trading_day(date(2024, 1, 15)) is True

        # Weekend (Saturday)
        assert is_trading_day(date(2024, 1, 13)) is False

        # Weekend (Sunday)
        assert is_trading_day(date(2024, 1, 14)) is False

    def test_get_trading_days_between(self):
        """Test getting trading days between dates"""
        from utils.date_utils import get_trading_days_between

        # One week period
        result = get_trading_days_between("2024-01-15", "2024-01-19")
        assert len(result) == 5  # Mon-Fri

        # Invalid dates
        result = get_trading_days_between("invalid", "2024-01-19")
        assert result == []

    def test_format_date(self):
        """Test date formatting"""
        from utils.date_utils import format_date
        result = format_date(date(2024, 1, 15))
        assert result == "2024-01-15"

    def test_days_between(self):
        """Test days between calculation"""
        from utils.date_utils import days_between
        assert days_between("2024-01-01", "2024-01-10") == 9
        assert days_between("2024-01-10", "2024-01-01") == 9  # Absolute value
        assert days_between("invalid", "2024-01-10") == 0
