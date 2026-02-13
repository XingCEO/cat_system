"""
Tests for EnhancedKLineService range handling.
"""
from datetime import date

import pandas as pd

from services.enhanced_kline_service import EnhancedKLineService


class TestEnhancedKLineServiceRangeHandling:
    def setup_method(self):
        self.service = EnhancedKLineService()

    def test_get_missing_ranges_when_cache_empty(self):
        df = pd.DataFrame()
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        missing = self.service._get_missing_ranges(df, start, end)
        assert missing == [(start, end)]

    def test_get_missing_ranges_left_edge_gap(self):
        df = pd.DataFrame(
            {"date": ["2024-07-01", "2024-07-02", "2024-12-31"]}
        )
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        missing = self.service._get_missing_ranges(df, start, end)
        assert missing == [(date(2024, 1, 1), date(2024, 6, 30))]

    def test_get_missing_ranges_right_edge_gap(self):
        df = pd.DataFrame(
            {"date": ["2024-01-02", "2024-01-03", "2024-06-30"]}
        )
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        missing = self.service._get_missing_ranges(df, start, end)
        assert missing == [
            (date(2024, 1, 1), date(2024, 1, 1)),
            (date(2024, 7, 1), date(2024, 12, 31)),
        ]

    def test_clip_to_date_range(self):
        df = pd.DataFrame(
            {
                "date": ["2023-12-31", "2024-01-02", "2024-06-01", "2025-01-01"],
                "close": [10, 11, 12, 13],
                "open": [10, 11, 12, 13],
                "high": [10, 11, 12, 13],
                "low": [10, 11, 12, 13],
                "volume": [1, 1, 1, 1],
            }
        )

        clipped = self.service._clip_to_date_range(
            df,
            date(2024, 1, 1),
            date(2024, 12, 31),
        )
        assert len(clipped) == 2
        assert clipped.iloc[0]["date"] == date(2024, 1, 2)
        assert clipped.iloc[1]["date"] == date(2024, 6, 1)
