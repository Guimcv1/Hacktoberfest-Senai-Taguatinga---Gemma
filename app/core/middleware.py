from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

logger = logging.getLogger("studybuddy")

_SENSITIVE_PATHS = {"/api/auth/login", "/api/auth/register"}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        settings = get_settings()
        limit = settings.rate_limit_per_minute
        if request.url.path in _SENSITIVE_PATHS and settings.environment != "test":
            limit = max(5, min(limit, 20))
        key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
        now = time.time()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= limit:
                logger.warning("Rate limit excedido para rota %s", request.url.path)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Muitas requisições. Tente novamente em instantes."},
                )
            bucket.append(now)
        return await call_next(request)
