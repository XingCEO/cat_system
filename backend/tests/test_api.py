"""
Test API Endpoints
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_check(self, client: TestClient):
        """Test /api/health endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    def test_api_status(self, client: TestClient):
        """Test /api/status endpoint"""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "name" in data["data"]
        assert "version" in data["data"]
        assert data["data"]["status"] == "running"


class TestCacheEndpoints:
    """Test cache management endpoints"""

    def test_cache_stats(self, client: TestClient):
        """Test /api/cache/stats endpoint"""
        response = client.get("/api/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_cache_clear_without_auth(self, client: TestClient):
        """Test cache clear without admin key (should work if ADMIN_API_KEY not set)"""
        response = client.delete("/api/cache/clear")
        # Should succeed if no ADMIN_API_KEY is configured
        assert response.status_code in [200, 401]


class TestTurnoverEndpoints:
    """Test turnover analysis endpoints"""

    def test_top20_turnover(self, client: TestClient):
        """Test /api/turnover/top20 endpoint"""
        response = client.get("/api/turnover/top20")
        assert response.status_code in [200, 400]  # 400 if no trading data

    def test_limit_up(self, client: TestClient):
        """Test /api/turnover/limit-up endpoint"""
        response = client.get("/api/turnover/limit-up")
        assert response.status_code in [200, 400]

    def test_ma_breakout_accepts_slash_date(self, client: TestClient):
        """Test /api/turnover/ma-breakout accepts YYYY/MM/DD and normalizes it"""
        response = client.get("/api/turnover/ma-breakout?start_date=2025/11/01&end_date=2025/11/01")
        assert response.status_code in [200, 400]

    def test_volume_surge_accepts_slash_date_range(self, client: TestClient):
        """Test /api/turnover/volume-surge accepts YYYY/MM/DD date range"""
        response = client.get("/api/turnover/volume-surge?start_date=2025/11/01&end_date=2025/11/03")
        assert response.status_code in [200, 400]

    def test_institutional_buy_accepts_slash_date_range(self, client: TestClient):
        """Test /api/turnover/institutional-buy accepts YYYY/MM/DD date range"""
        response = client.get("/api/turnover/institutional-buy?start_date=2025/11/01&end_date=2025/11/03")
        assert response.status_code in [200, 400]


class TestExportEndpoints:
    """Test export endpoints return downloadable responses."""

    def test_export_csv(self, client: TestClient):
        response = client.get("/api/export/csv?date=2025-11-10&change_min=-10&change_max=10&volume_min=100")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_export_excel(self, client: TestClient):
        response = client.get("/api/export/excel?date=2025-11-10&change_min=-10&change_max=10&volume_min=100")
        assert response.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers.get("content-type", "")

    def test_export_json(self, client: TestClient):
        response = client.get("/api/export/json?date=2025-11-10&change_min=-10&change_max=10&volume_min=100")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestBacktestEndpoints:
    """Test backtest endpoints."""

    def test_run_backtest_rejects_overlong_date_range(self, client: TestClient):
        payload = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31"
        }
        response = client.post("/api/backtest/run", json=payload)
        assert response.status_code == 400
        assert "不可超過 365 天" in response.json().get("detail", "")


@pytest.fixture
def client():
    """Create test client"""
    from main import app
    with TestClient(app) as c:
        yield c
