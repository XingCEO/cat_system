"""
Test Validators
"""
import pytest
from utils.validators import (
    validate_symbol,
    validate_date,
    validate_date_range,
    validate_percentage_range,
    validate_volume,
    validate_price,
    sanitize_string
)


class TestValidateSymbol:
    """Test stock symbol validation"""

    def test_valid_4_digit_symbol(self):
        is_valid, error = validate_symbol("2330")
        assert is_valid is True
        assert error is None

    def test_valid_6_digit_symbol(self):
        is_valid, error = validate_symbol("006208")
        assert is_valid is True
        assert error is None

    def test_empty_symbol(self):
        is_valid, error = validate_symbol("")
        assert is_valid is False
        assert "不可為空" in error

    def test_invalid_symbol_with_letters(self):
        is_valid, error = validate_symbol("AAPL")
        assert is_valid is False
        assert "無效" in error

    def test_invalid_symbol_too_short(self):
        is_valid, error = validate_symbol("123")
        assert is_valid is False


class TestValidateDate:
    """Test date validation"""

    def test_valid_date(self):
        is_valid, error = validate_date("2024-01-15")
        assert is_valid is True
        assert error is None

    def test_empty_date_is_optional(self):
        is_valid, error = validate_date("")
        assert is_valid is True

    def test_invalid_date_format(self):
        is_valid, error = validate_date("01-15-2024")
        assert is_valid is False
        assert "格式" in error

    def test_date_before_2000(self):
        is_valid, error = validate_date("1999-12-31")
        assert is_valid is False
        assert "2000" in error


class TestValidateDateRange:
    """Test date range validation"""

    def test_valid_range(self):
        is_valid, error = validate_date_range("2024-01-01", "2024-01-31")
        assert is_valid is True
        assert error is None

    def test_start_after_end(self):
        is_valid, error = validate_date_range("2024-01-31", "2024-01-01")
        assert is_valid is False
        assert "晚於" in error

    def test_range_too_long(self):
        is_valid, error = validate_date_range("2023-01-01", "2024-12-31", max_days=365)
        assert is_valid is False
        assert "超過" in error


class TestValidatePercentageRange:
    """Test percentage range validation"""

    def test_valid_range(self):
        is_valid, error = validate_percentage_range(1.0, 10.0)
        assert is_valid is True

    def test_min_greater_than_max(self):
        is_valid, error = validate_percentage_range(10.0, 1.0)
        assert is_valid is False
        assert "不可大於" in error

    def test_out_of_range(self):
        is_valid, error = validate_percentage_range(-200.0, None)
        assert is_valid is False
        assert "超出" in error


class TestValidateVolume:
    """Test volume validation"""

    def test_valid_volume(self):
        is_valid, error = validate_volume(1000)
        assert is_valid is True

    def test_negative_volume(self):
        is_valid, error = validate_volume(-100)
        assert is_valid is False
        assert "負數" in error

    def test_none_volume(self):
        is_valid, error = validate_volume(None)
        assert is_valid is True


class TestValidatePrice:
    """Test price validation"""

    def test_valid_price_range(self):
        is_valid, error = validate_price(10.0, 100.0)
        assert is_valid is True

    def test_min_greater_than_max(self):
        is_valid, error = validate_price(100.0, 10.0)
        assert is_valid is False

    def test_zero_price(self):
        is_valid, error = validate_price(0, None)
        assert is_valid is False


class TestSanitizeString:
    """Test string sanitization"""

    def test_trim_whitespace(self):
        result = sanitize_string("  hello  ")
        assert result == "hello"

    def test_truncate_long_string(self):
        result = sanitize_string("a" * 200, max_length=100)
        assert len(result) == 100

    def test_empty_string(self):
        result = sanitize_string("")
        assert result == ""
