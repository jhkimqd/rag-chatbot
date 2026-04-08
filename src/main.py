"""FastAPI entry point for the Polygon Hybrid Bot."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.router.protocol_switch import route_input

logger = logging.getLogger(__name__)


# --- In-memory rate limiter with TTL eviction ---

_MAX_TRACKED_IPS = 50_000
_WINDOW_SECONDS = 60.0
_CLEANUP_INTERVAL = 300.0
_DAY_SECONDS = 86_400.0

_rate_store: dict[str, list[float]] = {}
_daily_store: dict[str, list[float]] = {}
_last_cleanup: float = 0.0


def _evict_stale_entries() -> None:
    """Periodically remove expired entries to prevent memory exhaustion."""
    global _last_cleanup  # noqa: PLW0603
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    stale_keys = [
        k for k, timestamps in _rate_store.items()
        if not timestamps or now - timestamps[-1] >= _WINDOW_SECONDS
    ]
    for k in stale_keys:
        del _rate_store[k]

    # Evict expired daily entries
    stale_daily = [
        k for k, timestamps in _daily_store.items()
        if not timestamps or now - timestamps[0] >= _DAY_SECONDS
    ]
    for k in stale_daily:
        del _daily_store[k]


def _check_rate_limit(key: str) -> bool:
    """Return True if the request is within per-minute rate limits."""
    _evict_stale_entries()

    if key not in _rate_store and len(_rate_store) >= _MAX_TRACKED_IPS:
        return False

    now = time.monotonic()
    timestamps = _rate_store.get(key, [])
    timestamps = [t for t in timestamps if now - t < _WINDOW_SECONDS]
    if len(timestamps) >= settings.rate_limit_per_minute:
        _rate_store[key] = timestamps
        return False
    timestamps.append(now)
    _rate_store[key] = timestamps
    return True


def _check_daily_limit(key: str) -> bool:
    """Return True if the request is within daily request budget."""
    now = time.monotonic()
    timestamps = _daily_store.get(key, [])
    timestamps = [t for t in timestamps if now - t < _DAY_SECONDS]
    if len(timestamps) >= settings.daily_request_limit:
        _daily_store[key] = timestamps
        return False
    timestamps.append(now)
    _daily_store[key] = timestamps
    return True


# --- Auth dependency (pre-computed hash for constant-time comparison) ---

_api_key_hash: bytes | None = (
    hashlib.sha256(settings.chatbot_api_key.encode()).digest()
    if settings.chatbot_api_key
    else None
)


async def verify_api_key(request: Request) -> str:
    """Verify the X-API-Key header if authentication is configured."""
    if _api_key_hash is None:
        return "anonymous"
    api_key = request.headers.get("X-API-Key", "")
    if not api_key or not hmac.compare_digest(
        hashlib.sha256(api_key.encode()).digest(),
        _api_key_hash,
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return "authenticated"


# --- App setup ---

_is_prod = settings.environment == "production"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=settings.log_level.upper())
    logger.info("Polygon Hybrid Bot starting up (env=%s)", settings.environment)
    yield
    logger.info("Polygon Hybrid Bot shutting down")


app = FastAPI(
    title="Polygon Hybrid Bot",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# --- Security middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if _is_prod else ["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
    allow_credentials=False,
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:  # noqa: ANN001
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    if _is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.max_message_length)
    user_id: str = Field(default="anonymous", max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    channel: str = Field(default="web", max_length=20)


class ChatResponse(BaseModel):
    reply: str
    source: str
    route: str
    metadata: dict | None = None


@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    payload: dict = {"service": "Polygon Hybrid Bot"}
    if not _is_prod:
        payload["version"] = "0.1.0"
        payload["endpoints"] = {
            "chat": "POST /chat",
            "health": "GET /health",
            "docs": "GET /docs  (development only)",
        }
    return JSONResponse(payload)


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
    _auth: str = Depends(verify_api_key),
) -> ChatResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    if not _check_daily_limit(client_ip):
        raise HTTPException(status_code=429, detail="Daily request limit reached. Try again tomorrow.")

    try:
        result = await asyncio.wait_for(
            route_input(message=body.message, user_id=body.user_id),
            timeout=settings.request_timeout_seconds,
        )
    except asyncio.TimeoutError:
        return ChatResponse(
            reply="Request timed out. Please try a simpler question.",
            source="system",
            route="timeout",
        )
    return ChatResponse(**result)


@app.get("/health")
async def healthcheck() -> dict:
    payload: dict = {"status": "ok"}
    if not _is_prod:
        payload["version"] = "0.1.0"
    return payload


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
