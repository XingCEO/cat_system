"""Tests for config/version consistency and API endpoint signatures"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestVersionConsistency:
    def test_config_version_matches_main(self):
        from config import get_settings
        settings = get_settings()
        assert settings.app_version == "2.0.0"

    def test_debug_release_env_is_false(self, monkeypatch):
        from config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("DEBUG", "release")
        try:
            assert get_settings().debug is False
        finally:
            get_settings.cache_clear()


class TestDatabaseEngineOptions:
    def test_sqlite_engine_waits_for_short_write_locks(self):
        from database import _engine_kwargs

        kwargs = _engine_kwargs("sqlite+aiosqlite:///./twse_filter.db")
        assert kwargs["connect_args"]["timeout"] >= 30

    def test_postgres_engine_does_not_receive_sqlite_connect_args(self):
        from database import _engine_kwargs

        kwargs = _engine_kwargs("postgresql+asyncpg://user:pass@example/db")
        assert "connect_args" not in kwargs


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
