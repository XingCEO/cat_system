"""
High Turnover Analyzer - Core service for high turnover rate limit-up analysis

This module has been refactored into smaller, focused components:
- base.py: Core turnover calculation and limit-up detection
- technical.py: MA breakout and technical indicators
- institutional.py: Institutional investor analysis
- history.py: Historical data analysis
- top200_filters.py: Top 200 filtering utilities
- combo_filter.py: Composite filter combinations

The HighTurnoverAnalyzer class now uses mixins to compose functionality.
"""
import logging

from services.analyzers.base import BaseAnalyzer
from services.analyzers.technical import TechnicalAnalyzerMixin
from services.analyzers.institutional import InstitutionalAnalyzerMixin
from services.analyzers.history import HistoryAnalyzerMixin
from services.analyzers.top200_filters import Top200FiltersMixin
from services.analyzers.combo_filter import ComboFilterMixin

logger = logging.getLogger(__name__)


class HighTurnoverAnalyzer(
    BaseAnalyzer,
    TechnicalAnalyzerMixin,
    InstitutionalAnalyzerMixin,
    HistoryAnalyzerMixin,
    Top200FiltersMixin,
    ComboFilterMixin
):
    """
    高周轉率漲停股分析服務

    重構後使用 Mixin 模式組合功能：
    - BaseAnalyzer: 核心周轉率計算、漲停判定
    - TechnicalAnalyzerMixin: 均線突破、技術指標
    - InstitutionalAnalyzerMixin: 法人買賣超分析
    - HistoryAnalyzerMixin: 歷史資料分析
    - Top200FiltersMixin: 前200名篩選器
    - ComboFilterMixin: 複合條件篩選
    """

    def __init__(self):
        super().__init__()


# Global instance
high_turnover_analyzer = HighTurnoverAnalyzer()
