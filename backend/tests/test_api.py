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


@pytest.fixture
def client():
    """Create test client"""
    from main import app
    with TestClient(app) as c:
        yield c
