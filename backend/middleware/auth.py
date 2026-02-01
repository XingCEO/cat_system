"""
Optional Authentication Middleware
提供可選的 API Key 認證，不影響現有使用
"""
import os
import logging
from typing import Optional, Callable
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# 從環境變數讀取管理員 API Key（可選）
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# API Key Header
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def get_optional_admin_key(
    api_key: Optional[str] = Depends(api_key_header)
) -> Optional[str]:
    """
    可選的管理員 API Key 驗證
    如果未設定 ADMIN_API_KEY 環境變數，則跳過驗證
    """
    return api_key


def require_admin_key(
    api_key: Optional[str] = Depends(get_optional_admin_key)
) -> bool:
    """
    要求管理員 API Key（僅在設定了 ADMIN_API_KEY 時生效）

    使用方式：
    @router.delete("/cache", dependencies=[Depends(require_admin_key)])
    async def clear_cache():
        ...
    """
    # 如果未設定 ADMIN_API_KEY，允許所有請求（向後相容）
    if not ADMIN_API_KEY:
        return True

    # 如果設定了 ADMIN_API_KEY，驗證請求
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="需要管理員權限",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if api_key != ADMIN_API_KEY:
        logger.warning("Invalid admin key attempted")
        raise HTTPException(
            status_code=403,
            detail="無效的管理員金鑰"
        )

    return True


class OptionalAuthMiddleware:
    """
    可選認證中間件
    用於記錄認證嘗試，不阻擋請求
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # 記錄帶有認證標頭的請求
            headers = dict(scope.get("headers", []))
            if b"x-admin-key" in headers:
                logger.debug("Request with admin key received")

        await self.app(scope, receive, send)
