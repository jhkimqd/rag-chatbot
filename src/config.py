"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

_config_logger = logging.getLogger(__name__)

_ALLOWED_DATADOG_SITES = frozenset({
    "datadoghq.com",
    "datadoghq.eu",
    "us3.datadoghq.com",
    "us5.datadoghq.com",
    "ap1.datadoghq.com",
    "ddog-gov.com",
})


class Settings(BaseSettings):
    # LLM backend: "anthropic" or "ollama"
    llm_backend: str = "anthropic"

    # Anthropic
    anthropic_api_key: str = ""

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_classifier_model: str = "llama3.2"

    # Polygon RPC
    polygon_rpc_url: str = "https://polygon-rpc.com"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "polygon-docs"

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""

    # Datadog
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_site: str = "datadoghq.com"

    # Incident.io
    incident_io_api_key: str = ""

    # Server
    environment: str = "development"
    host: str = "0.0.0.0"  # noqa: S104 — intentional for container deployments
    port: int = 8000
    log_level: str = "info"
    chatbot_api_key: str = ""
    rate_limit_per_minute: int = Field(default=30, ge=1)
    daily_request_limit: int = Field(default=200, ge=1)
    request_timeout_seconds: int = Field(default=60, ge=10, le=300)
    max_message_length: int = Field(default=2000, ge=1, le=10000)

    # Models
    classifier_model: str = "claude-haiku-4-5-20251001"
    reasoning_model: str = "claude-sonnet-4-6"

    # RAG (local sentence-transformers model, no API key needed)
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        backend = os.getenv("LLM_BACKEND", "anthropic").lower()
        if not v and backend == "anthropic" and os.getenv("TESTING") != "1":
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env == "production":
                raise ValueError(
                    "ANTHROPIC_API_KEY is required in production when using "
                    "the anthropic backend. Set it in .env or as an environment "
                    "variable, or use LLM_BACKEND=ollama."
                )
        return v

    @field_validator("chatbot_api_key")
    @classmethod
    def validate_chatbot_api_key(cls, v: str) -> str:
        """Enforce API key in production; warn in development."""
        if not v and os.getenv("TESTING") != "1":
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env == "production":
                raise ValueError(
                    "CHATBOT_API_KEY is required in production. "
                    "Set it in .env or as an environment variable."
                )
            _config_logger.warning(
                "CHATBOT_API_KEY is not set — /chat endpoint is unauthenticated. "
                "This is acceptable in development but must be set for production."
            )
        return v

    @field_validator("datadog_site")
    @classmethod
    def validate_datadog_site(cls, v: str) -> str:
        """Restrict datadog_site to known Datadog domains to prevent SSRF."""
        if v and v not in _ALLOWED_DATADOG_SITES:
            raise ValueError(
                f"Invalid DATADOG_SITE '{v}'. "
                f"Allowed values: {', '.join(sorted(_ALLOWED_DATADOG_SITES))}"
            )
        return v

    @field_validator("polygon_rpc_url")
    @classmethod
    def validate_polygon_rpc_url(cls, v: str) -> str:
        """Ensure RPC URL uses HTTPS (except localhost for development)."""
        from urllib.parse import urlparse

        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"POLYGON_RPC_URL must use http or https scheme, got '{parsed.scheme}'"
            )
        is_local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme != "https" and not is_local:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env == "production":
                raise ValueError(
                    "POLYGON_RPC_URL must use HTTPS in production."
                )
            _config_logger.warning(
                "POLYGON_RPC_URL is using HTTP for a non-local host. "
                "Use HTTPS in production."
            )
        return v

    @field_validator("qdrant_url")
    @classmethod
    def validate_qdrant_url(cls, v: str) -> str:
        """Warn if Qdrant API key is used without TLS."""
        return v

    def model_post_init(self, __context: object) -> None:
        """Cross-field validation after all fields are set."""
        if self.qdrant_api_key and not self.qdrant_url.startswith("https://"):
            from urllib.parse import urlparse

            parsed = urlparse(self.qdrant_url)
            is_local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if not is_local:
                _config_logger.warning(
                    "QDRANT_API_KEY is set but QDRANT_URL does not use HTTPS. "
                    "The API key will be transmitted in cleartext."
                )


settings = Settings()
