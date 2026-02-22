"""Tests for config/version consistency and API endpoint signatures"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestVersionConsistency:
    def test_config_version_matches_main(self):
        from config import get_settings
        settings = get_settings()
        assert settings.app_version == "2.0.0"


class TestTurnoverEndpointSignatures:
    """Verify volume-surge and institutional-buy service methods accept end_date"""

    def test_volume_surge_accepts_end_date(self):
        from services.high_turnover_analyzer import HighTurnoverAnalyzer
        import inspect
        sig = inspect.signature(HighTurnoverAnalyzer.get_volume_surge)
        assert "end_date" in sig.parameters

    def test_institutional_buy_accepts_end_date(self):
        from services.high_turnover_analyzer import HighTurnoverAnalyzer
        import inspect
        sig = inspect.signature(HighTurnoverAnalyzer.get_institutional_buy)
        assert "end_date" in sig.parameters

    def test_create_track_exists(self):
        from services.high_turnover_analyzer import HighTurnoverAnalyzer
        assert hasattr(HighTurnoverAnalyzer, "create_track")

    def test_get_track_stats_exists(self):
        from services.high_turnover_analyzer import HighTurnoverAnalyzer
        assert hasattr(HighTurnoverAnalyzer, "get_track_stats")
