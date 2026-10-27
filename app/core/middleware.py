from __future__ import annotations

import logging
import math
import re
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable
from contextvars import ContextVar
from threading import Lock

from fastapi import HTTPException
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

logger = logging.getLogger("studybuddy")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_UPLOAD_PATH = "/api/documents"
_JSON_BODY_LIMIT = 1024 * 1024
_MULTIPART_OVERHEAD = 1024 * 1024
_AUTH_GROUPS = {"/api/auth/login", "/api/auth/register"}
_ROUTE_GROUPS = (
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth",
    "/api/documents",
    "/api/conversations",
    "/api/chat",
)


class RequestContextMiddleware:
    """Propaga X-Request-ID e converte erros inesperados em 500 JSON ainda dentro do CORS."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_PATTERN.fullmatch(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("Erro interno não tratado em %s %s", scope.get("method"), scope.get("path"))
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={"detail": "Erro interno. Tente novamente mais tarde."},
            )
            await response(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)


class EmptyJsonBodyMiddleware:
    """POST /api/conversations sem corpo (ou null) vira {}, para criar conversa sem PDF."""

    _PATH = "/api/conversations"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        if scope.get("path", "").rstrip("/") != self._PATH:
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self.app(scope, receive, send)
                return
            chunks.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        body = b"".join(chunks).strip()
        if not body or body in {b"null", b"undefined", b"none"}:
            body = b"{}"
            headers = [
                (key, value)
                for key, value in scope.get("headers", [])
                if key not in {b"content-type", b"content-length"}
            ]
            headers.append((b"content-type", b"application/json"))
            headers.append((b"content-length", str(len(body)).encode()))
            scope["headers"] = headers

        sent = False

        async def replay() -> Message:
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


class BodySizeLimitMiddleware:
    """Recusa corpos grandes antes de autenticar ou interpretar a requisição."""

    def __init__(self, app: ASGIApp, settings_provider: Callable = get_settings) -> None:
        self.app = app
        self._settings_provider = settings_provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        is_upload = scope["path"].rstrip("/") == _UPLOAD_PATH
        if is_upload:
            limit = self._settings_provider().max_pdf_size_bytes + _MULTIPART_OVERHEAD
            detail = "Arquivo excede o tamanho máximo permitido."
        else:
            limit = _JSON_BODY_LIMIT
            detail = "A requisição excede o tamanho máximo permitido."

        declared = _content_length(scope)
        if declared is not None and declared > limit:
            response = JSONResponse(status_code=413, content={"detail": detail}, headers={"Connection": "close"})
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail=detail)
            return message

        await self.app(scope, limited_receive, send)


class RateLimitMiddleware:
    """Janela deslizante de 60 s por IP e grupo de rotas, em memória deste processo."""

    window_seconds = 60.0
    max_tracked_keys = 10_000

    def __init__(
        self,
        app: ASGIApp,
        settings_provider: Callable = get_settings,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self._settings_provider = settings_provider
        self._clock = clock
        # Ordenado pelo último acesso: as chaves vencidas ficam sempre no início.
        self._hits: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        settings = self._settings_provider()
        group = _route_group(scope["path"])
        limit = settings.rate_limit_auth_per_minute if group in _AUTH_GROUPS else settings.rate_limit_per_minute
        if limit <= 0:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        retry_after = self._register_hit((client[0] if client else "unknown", group), limit)
        if retry_after is not None:
            logger.warning("Rate limit excedido para o grupo %s", group)
            response = JSONResponse(
                status_code=429,
                content={"detail": "Muitas requisições. Tente novamente em instantes."},
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    @property
    def tracked_keys(self) -> int:
        return len(self._hits)

    def _register_hit(self, key: tuple[str, str], limit: int) -> int | None:
        now = self._clock()
        with self._lock:
            self._evict_stale(now)
            bucket = self._hits.setdefault(key, deque())
            self._hits.move_to_end(key)
            while bucket and now - bucket[0] >= self.window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, math.ceil(self.window_seconds - (now - bucket[0])))
            bucket.append(now)
            while len(self._hits) > self.max_tracked_keys:
                self._hits.popitem(last=False)
            return None

    def _evict_stale(self, now: float) -> None:
        while self._hits:
            oldest = next(iter(self._hits.values()))
            if oldest and now - oldest[-1] < self.window_seconds:
                return
            self._hits.popitem(last=False)


def _route_group(path: str) -> str:
    for prefix in _ROUTE_GROUPS:
        if path == prefix or path.startswith(prefix + "/"):
            return prefix
    return "other"


def _content_length(scope: Scope) -> int | None:
    raw = Headers(scope=scope).get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
