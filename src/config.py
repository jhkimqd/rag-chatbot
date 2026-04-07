"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

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
        import os

        if not v and os.getenv("TESTING") != "1":
            raise ValueError(
                "ANTHROPIC_API_KEY is required. Set it in .env or as an environment variable."
            )
        return v


settings = Settings()
