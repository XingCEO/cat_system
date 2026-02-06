"""
Test Technical Analysis - Unit tests for MA strategies and technical indicators
"""
import pytest
from unittest.mock import AsyncMock, patch
import pandas as pd
import numpy as np

from services.technical_analysis import TechnicalAnalyzer, calculate_all_indicators


class TestTechnicalAnalyzer:
    """Test TechnicalAnalyzer class"""

    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    # ===== MA Calculation Tests =====

    def test_calculate_ma_valid(self):
        """Test MA calculation with valid data"""
        prices = [100, 98, 102, 99, 101]
        result = self.analyzer.calculate_ma(prices, 5)
        assert result == 100.0

    def test_calculate_ma_insufficient_data(self):
        """Test MA calculation with insufficient data"""
        prices = [100, 98, 102]
        result = self.analyzer.calculate_ma(prices, 5)
        assert result is None

    def test_calculate_ma_exact_period(self):
        """Test MA calculation with exactly period length"""
        prices = [10, 20, 30, 40, 50]
        result = self.analyzer.calculate_ma(prices, 5)
        assert result == 30.0

    # ===== RSI Calculation Tests =====

    def test_calculate_rsi_valid(self):
        """Test RSI calculation with valid data"""
        # Prices: 100, 99, 101, 98, 102, 97, 103, 96, 104, 95, 105, 94, 106, 93, 107, 92
        prices = [100 + (i % 2) * 7 - 3 for i in range(16)]
        result = self.analyzer.calculate_rsi(prices, 14)
        assert result is not None
        assert 0 <= result <= 100

    def test_calculate_rsi_all_gains(self):
        """Test RSI with all positive changes (should be 100)"""
        prices = [115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        result = self.analyzer.calculate_rsi(prices, 14)
        assert result == 100.0

    def test_calculate_rsi_all_losses(self):
        """Test RSI with all negative changes (should be 0)"""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115]
        result = self.analyzer.calculate_rsi(prices, 14)
        assert result == 0.0

    def test_calculate_rsi_no_change(self):
        """Test RSI with no price change (should be 50)"""
        prices = [100] * 16
        result = self.analyzer.calculate_rsi(prices, 14)
        assert result == 50.0

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI with insufficient data"""
        prices = [100, 101, 102]
        result = self.analyzer.calculate_rsi(prices, 14)
        assert result is None

    # ===== Golden Cross / Death Cross Tests =====

    def test_is_golden_cross_true(self):
        """Test golden cross detection"""
        ma_short = [105, 95]  # Today > yesterday, crossed above
        ma_long = [100, 100]
        result = self.analyzer.is_golden_cross(ma_short, ma_long)
        assert result is True

    def test_is_golden_cross_false(self):
        """Test no golden cross"""
        ma_short = [105, 105]  # Already above
        ma_long = [100, 100]
        result = self.analyzer.is_golden_cross(ma_short, ma_long)
        assert result is False

    def test_is_death_cross_true(self):
        """Test death cross detection"""
        ma_short = [95, 105]  # Today < yesterday, crossed below
        ma_long = [100, 100]
        result = self.analyzer.is_death_cross(ma_short, ma_long)
        assert result is True

    def test_is_death_cross_false(self):
        """Test no death cross"""
        ma_short = [95, 95]  # Already below
        ma_long = [100, 100]
        result = self.analyzer.is_death_cross(ma_short, ma_long)
        assert result is False

    def test_cross_insufficient_data(self):
        """Test cross detection with insufficient data"""
        ma_short = [100]
        ma_long = [100, 100]
        assert self.analyzer.is_golden_cross(ma_short, ma_long) is False
        assert self.analyzer.is_death_cross(ma_short, ma_long) is False


class TestCalculateAllIndicators:
    """Test calculate_all_indicators function"""

    def test_calculate_all_indicators_valid(self):
        """Test indicator calculation with valid DataFrame"""
        # Create sample data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(95, 105, 100),
            'high': np.random.uniform(100, 110, 100),
            'low': np.random.uniform(90, 100, 100),
            'close': np.random.uniform(95, 105, 100),
            'volume': np.random.randint(1000000, 5000000, 100)
        })

        result = calculate_all_indicators(df)

        # Check that indicators were added
        assert 'SMA_5' in result.columns
        assert 'SMA_20' in result.columns
        assert 'RSI_14' in result.columns
        assert 'MACD_12_26_9' in result.columns
        assert 'STOCHk_9_3_3' in result.columns

    def test_calculate_all_indicators_empty(self):
        """Test with empty DataFrame"""
        df = pd.DataFrame()
        result = calculate_all_indicators(df)
        assert result.empty

    def test_calculate_all_indicators_insufficient(self):
        """Test with insufficient data (less than 14 rows)"""
        df = pd.DataFrame({
            'close': [100, 101, 102, 103, 104]
        })
        result = calculate_all_indicators(df)
        # Should return original df without modification
        assert len(result) == 5


class TestSafeMA:
    """Test _safe_ma static method from BaseAnalyzer"""

    def test_safe_ma_valid(self):
        """Test safe MA with valid values"""
        from services.analyzers.base import BaseAnalyzer
        values = [10, 20, 30, 40, 50]
        result = BaseAnalyzer._safe_ma(values, 5)
        assert result == 30.0

    def test_safe_ma_with_none(self):
        """Test safe MA with None values"""
        from services.analyzers.base import BaseAnalyzer
        values = [10, None, 30, 40, 50]
        result = BaseAnalyzer._safe_ma(values, 5)
        assert result is None  # Not enough valid values

    def test_safe_ma_with_nan(self):
        """Test safe MA with NaN values"""
        from services.analyzers.base import BaseAnalyzer
        values = [10, float('nan'), 30, 40, 50]
        result = BaseAnalyzer._safe_ma(values, 5)
        assert result is None

    def test_safe_ma_partial_valid(self):
        """Test safe MA with some valid values"""
        from services.analyzers.base import BaseAnalyzer
        values = [10, 20, 30, None, None, None]
        result = BaseAnalyzer._safe_ma(values, 3)
        assert result == 20.0  # Only first 3 are used


class TestLimitUpDetection:
    """Test limit-up price calculation and detection"""

    def test_calculate_limit_up_price(self):
        """Test limit-up price calculation (Taiwan uses 9.9% threshold with tick rounding)"""
        from services.analyzers.base import BaseAnalyzer
        analyzer = BaseAnalyzer()

        # Test different price ranges - Taiwan uses 9.9% limit with tick size rounding
        # prev=100: 100*1.099=109.9, tick=0.5, floor(109.9/0.5)*0.5=109.5
        assert analyzer._calculate_limit_up_price(100) == 109.5
        # prev=50: 50*1.099=54.95, tick=0.1, floor(54.95/0.1)*0.1=54.9
        assert analyzer._calculate_limit_up_price(50) == 54.9
        # prev=10: 10*1.099=10.99, tick=0.05, floor(10.99/0.05)*0.05=10.95
        assert analyzer._calculate_limit_up_price(10) == 10.95

    def test_is_limit_up(self):
        """Test limit-up detection (Taiwan uses 9.9% threshold with tick rounding)"""
        from services.analyzers.base import BaseAnalyzer
        analyzer = BaseAnalyzer()

        # Exact limit-up (9.9% with tick rounding = 109.5 for prev=100)
        assert analyzer._is_limit_up(109.5, 100) is True
        # Close to limit-up (within 0.02 tolerance)
        assert analyzer._is_limit_up(109.49, 100) is True
        # Not limit-up
        assert analyzer._is_limit_up(105.0, 100) is False

    def test_is_limit_up_invalid_prices(self):
        """Test limit-up with invalid prices"""
        from services.analyzers.base import BaseAnalyzer
        analyzer = BaseAnalyzer()

        assert analyzer._is_limit_up(0, 100) is False
        assert analyzer._is_limit_up(100, 0) is False
        assert analyzer._is_limit_up(-10, 100) is False
