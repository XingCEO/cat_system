"""Admin token gate — 可透過 settings.require_admin_token=False 停用。"""
from fastapi import Header, HTTPException, status
from typing import Optional
from config import get_settings


def require_admin(
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """
    FastAPI dependency：驗證 admin token。

    驗證邏輯：
    - require_admin_token=False → 直接通過（local dev 無阻礙）
    - require_admin_token=True 且 admin_token 未設定 → 503（避免誤以為有 gate）
    - 已設 admin_token → 檢查 Authorization: Bearer <token> 或 X-Admin-Token header
    """
    settings = get_settings()

    if not settings.require_admin_token:
        return  # gate 已停用

    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoint disabled: ADMIN_TOKEN not configured",
        )

    provided: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()
    elif x_admin_token:
        provided = x_admin_token.strip()

    if provided != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )
