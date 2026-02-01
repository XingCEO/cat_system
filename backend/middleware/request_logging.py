"""
Request Logging Middleware
記錄所有 API 請求
"""
import time
import logging
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    請求日誌中間件
    記錄每個 API 請求的方法、路徑、狀態碼和處理時間
    """

    async def dispatch(self, request: Request, call_next):
        # 生成請求 ID
        request_id = str(uuid.uuid4())[:8]

        # 記錄開始時間
        start_time = time.perf_counter()

        # 處理請求
        response = await call_next(request)

        # 計算處理時間
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 記錄請求（排除健康檢查和靜態檔案）
        path = request.url.path
        if not path.startswith("/assets") and path not in ["/api/health", "/favicon.ico"]:
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2)
            }

            if response.status_code >= 500:
                logger.error(f"[{request_id}] {request.method} {path} - {response.status_code} ({duration_ms:.2f}ms)")
            elif response.status_code >= 400:
                logger.warning(f"[{request_id}] {request.method} {path} - {response.status_code} ({duration_ms:.2f}ms)")
            else:
                logger.info(f"[{request_id}] {request.method} {path} - {response.status_code} ({duration_ms:.2f}ms)")

        # 加入請求 ID 到回應標頭
        response.headers["X-Request-ID"] = request_id

        return response
