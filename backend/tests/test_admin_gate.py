"""
test_admin_gate.py
驗證 require_admin dependency 的 gate 行為：
  - require_admin_token=True  + admin_token 未設定  → 503
  - require_admin_token=True  + 錯誤 token          → 401
  - require_admin_token=True  + 正確 token          → 非 401/503
  - require_admin_token=False                       → 通過（任何 token）

使用 FastAPI dependency_overrides 控制 settings，
不真正啟動 DB / 背景任務。
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture()
def client_with_settings(monkeypatch):
    """
    回傳一個工廠 callable：
        make_client(require_admin_token, admin_token) -> TestClient

    每次呼叫都清除 lru_cache 並以 monkeypatch 注入環境變數，
    確保 get_settings() 回傳測試想要的值。
    使用 app.dependency_overrides 覆寫 require_admin。
    """
    from config import get_settings

    def make_client(require_admin_token: bool, admin_token: str | None):
        # 清除 lru_cache，強制重新建立 Settings
        get_settings.cache_clear()

        # 注入環境變數給 pydantic-settings 讀取
        monkeypatch.setenv("REQUIRE_ADMIN_TOKEN", str(require_admin_token).lower())
        if admin_token is not None:
            monkeypatch.setenv("ADMIN_TOKEN", admin_token)
        else:
            monkeypatch.delenv("ADMIN_TOKEN", raising=False)

        # 再次清除（確保 env 已寫入後重建）
        get_settings.cache_clear()

        # 延遲 import 避免模組層級的 settings = get_settings() 拿到舊值
        # 我們直接 patch app.core.auth 的 get_settings 呼叫
        import importlib
        import app.core.auth as auth_mod
        importlib.reload(auth_mod)

        # 重建 require_admin 函式（reload 後已使用新 settings）
        from app.core.auth import require_admin as fresh_require_admin

        # 建立輕量 FastAPI app，只掛要測試的 endpoint
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient

        test_app = FastAPI()

        @test_app.post("/api/cache/clear")
        async def _cache_clear(guard=Depends(fresh_require_admin)):
            return {"ok": True}

        @test_app.post("/api/data/refresh")
        async def _data_refresh(guard=Depends(fresh_require_admin)):
            return {"ok": True}

        @test_app.get("/api/v1/strategies")
        async def _strategies(guard=Depends(fresh_require_admin)):
            return []

        return TestClient(test_app, raise_server_exceptions=False)

    return make_client


# ──────────────────────────────────────────────
# /api/cache/clear gate 測試
# ──────────────────────────────────────────────

class TestCacheClearGate:

    def test_sync_blocked_without_token(self, client_with_settings):
        """gate 啟用且 ADMIN_TOKEN 未設定 → 503"""
        client = client_with_settings(require_admin_token=True, admin_token=None)
        resp = client.post("/api/cache/clear")
        assert resp.status_code == 503

    def test_sync_blocked_with_wrong_token(self, client_with_settings):
        """gate 啟用且 token 錯誤 → 401"""
        client = client_with_settings(require_admin_token=True, admin_token="secret")
        resp = client.post("/api/cache/clear", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_sync_allowed_with_correct_token(self, client_with_settings):
        """gate 啟用且 token 正確 → 非 401/503（endpoint 本身回傳 200）"""
        client = client_with_settings(require_admin_token=True, admin_token="secret")
        resp = client.post("/api/cache/clear", headers={"Authorization": "Bearer secret"})
        assert resp.status_code not in (401, 503)

    def test_sync_allowed_when_gate_disabled(self, client_with_settings):
        """gate 停用（require_admin_token=False）→ 不論 token 皆通過"""
        client = client_with_settings(require_admin_token=False, admin_token=None)
        resp = client.post("/api/cache/clear")
        assert resp.status_code not in (401, 503)

    def test_x_admin_token_header_accepted(self, client_with_settings):
        """也接受 X-Admin-Token header 傳遞 token"""
        client = client_with_settings(require_admin_token=True, admin_token="mytoken")
        resp = client.post("/api/cache/clear", headers={"X-Admin-Token": "mytoken"})
        assert resp.status_code not in (401, 503)

    def test_x_admin_token_wrong_rejected(self, client_with_settings):
        """X-Admin-Token header 帶錯誤值 → 401"""
        client = client_with_settings(require_admin_token=True, admin_token="mytoken")
        resp = client.post("/api/cache/clear", headers={"X-Admin-Token": "wrong"})
        assert resp.status_code == 401


# ──────────────────────────────────────────────
# /api/data/refresh gate 測試
# ──────────────────────────────────────────────

class TestDataRefreshGate:

    def test_data_refresh_blocked_without_token(self, client_with_settings):
        """data/refresh：gate 啟用且 ADMIN_TOKEN 未設定 → 503"""
        client = client_with_settings(require_admin_token=True, admin_token=None)
        resp = client.post("/api/data/refresh")
        assert resp.status_code == 503

    def test_data_refresh_blocked_with_wrong_token(self, client_with_settings):
        """data/refresh：gate 啟用且 token 錯誤 → 401"""
        client = client_with_settings(require_admin_token=True, admin_token="secret")
        resp = client.post("/api/data/refresh", headers={"Authorization": "Bearer bad"})
        assert resp.status_code == 401

    def test_data_refresh_has_gate(self, client_with_settings):
        """data/refresh：正確 token → 通過 gate（非 401/503）"""
        client = client_with_settings(require_admin_token=True, admin_token="secret")
        resp = client.post("/api/data/refresh", headers={"Authorization": "Bearer secret"})
        assert resp.status_code not in (401, 503)


# ──────────────────────────────────────────────
# /api/v1/strategies gate 測試（模擬 list endpoint 加 gate）
# ──────────────────────────────────────────────

class TestStrategiesGate:

    def test_strategies_list_blocked_without_token(self, client_with_settings):
        """strategies：gate 啟用且 ADMIN_TOKEN 未設定 → 503"""
        client = client_with_settings(require_admin_token=True, admin_token=None)
        resp = client.get("/api/v1/strategies")
        assert resp.status_code == 503

    def test_strategies_list_blocked_with_wrong_token(self, client_with_settings):
        """strategies：gate 啟用且 token 錯誤 → 401"""
        client = client_with_settings(require_admin_token=True, admin_token="abc")
        resp = client.get("/api/v1/strategies", headers={"Authorization": "Bearer xyz"})
        assert resp.status_code == 401

    def test_strategies_list_has_gate(self, client_with_settings):
        """strategies：正確 token → 非 401/503"""
        client = client_with_settings(require_admin_token=True, admin_token="abc")
        resp = client.get("/api/v1/strategies", headers={"Authorization": "Bearer abc"})
        assert resp.status_code not in (401, 503)


# ──────────────────────────────────────────────
# require_admin 純函式單元測試（不起 HTTP server）
# ──────────────────────────────────────────────

class TestRequireAdminUnit:
    """直接呼叫 require_admin()，驗證在各 settings 組合下的行為"""

    def _call_require_admin(self, require_admin_token: bool, admin_token,
                            authorization=None, x_admin_token=None):
        """
        模擬 FastAPI 注入 Header 的方式直接呼叫 require_admin。
        """
        from unittest.mock import MagicMock, patch
        from app.core.auth import require_admin
        from fastapi import HTTPException

        mock_settings = MagicMock()
        mock_settings.require_admin_token = require_admin_token
        mock_settings.admin_token = admin_token

        with patch("app.core.auth.get_settings", return_value=mock_settings):
            try:
                require_admin(
                    authorization=authorization,
                    x_admin_token=x_admin_token,
                )
                return None  # 通過（無 exception）
            except HTTPException as e:
                return e.status_code

    def test_gate_disabled_always_passes(self):
        """gate 停用 → 無論 token 為何都通過"""
        code = self._call_require_admin(False, None)
        assert code is None

    def test_gate_enabled_no_admin_token_configured_returns_503(self):
        """gate 啟用但 admin_token 未設定 → 503"""
        code = self._call_require_admin(True, None)
        assert code == 503

    def test_gate_enabled_wrong_bearer_returns_401(self):
        """gate 啟用、token 已設定、帶錯誤 Bearer → 401"""
        code = self._call_require_admin(True, "correct", authorization="Bearer wrong")
        assert code == 401

    def test_gate_enabled_correct_bearer_passes(self):
        """gate 啟用、token 已設定、帶正確 Bearer → 通過"""
        code = self._call_require_admin(True, "correct", authorization="Bearer correct")
        assert code is None

    def test_gate_enabled_correct_x_admin_token_passes(self):
        """gate 啟用、token 已設定、透過 X-Admin-Token header → 通過"""
        code = self._call_require_admin(True, "correct", x_admin_token="correct")
        assert code is None

    def test_gate_enabled_no_header_returns_401(self):
        """gate 啟用、token 已設定、但完全沒帶 token → 401"""
        code = self._call_require_admin(True, "correct")
        assert code == 401
