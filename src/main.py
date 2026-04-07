"""FastAPI entry point for the Polygon Hybrid Bot."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.router.protocol_switch import route_input

logger = logging.getLogger(__name__)


# --- Simple in-memory rate limiter ---

_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(key: str) -> bool:
    """Return True if the request is within rate limits."""
    now = time.monotonic()
    window = 60.0
    _rate_store[key] = [t for t in _rate_store[key] if now - t < window]
    if len(_rate_store[key]) >= settings.rate_limit_per_minute:
        return False
    _rate_store[key].append(now)
    return True


# --- Auth dependency ---


async def verify_api_key(request: Request) -> str:
    """Verify the X-API-Key header if authentication is configured."""
    if not settings.chatbot_api_key:
        return "anonymous"
    api_key = request.headers.get("X-API-Key", "")
    if not api_key or not hmac.compare_digest(
        hashlib.sha256(api_key.encode()).digest(),
        hashlib.sha256(settings.chatbot_api_key.encode()).digest(),
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
    return JSONResponse({
        "service": "Polygon Hybrid Bot",
        "version": "0.1.0",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
            "docs": "GET /docs  (development only)",
        },
    })


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
    _auth: str = Depends(verify_api_key),
) -> ChatResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

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
    return {"status": "ok", "version": "0.1.0"}


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
