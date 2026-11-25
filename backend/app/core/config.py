"""Application settings, loaded from environment variables (and `.env.local` / `.env` files).

Every variable is documented in ``backend/.env.example``. Secrets have no defaults.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_DIR / ".env.local"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- application ----
    app_name: str = "MediOps Intelligence"
    app_subtitle: str = "AI-Powered Hospital Operations & Performance Intelligence."
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # ---- database (Neon Postgres pooled vs unpooled) ----
    database_url: str = Field(
        default="postgresql+psycopg://healthcare:healthcare@localhost:5432/healthcare_bi",
        description="SQLAlchemy URL using the psycopg 3 driver (Neon pooled URL for application queries).",
    )
    database_url_unpooled: str | None = Field(
        default=None,
        description="Direct (non-pooled) Neon PostgreSQL URL used for Alembic schema migrations.",
    )

    # ---- CORS ----
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://mediops-intelligence.netlify.app",
            "https://careops-web.onrender.com",
            "https://careops-web-uk4b.onrender.com",
        ],
        description="Comma-separated allowlist of browser origins.",
    )
    cors_origin_regex: str = Field(
        default=r"^https://[a-z0-9-]+(\.[a-z0-9-]+)*\.(netlify\.app|onrender\.com|vercel\.app)$",
        description="Regex for dynamic Netlify, Render, and Vercel frontend subdomains.",
    )

    # ---- auth / JWT ----
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "careops-intelligence"
    jwt_audience: str = "careops-intelligence-web"
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=240)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = True
    cookie_samesite: Literal["strict", "lax", "none"] = "strict"
    refresh_cookie_name: str = "careops_refresh"

    # ---- seed accounts (all values from env; never committed) ----
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")
    manager_email: str = ""
    manager_password: SecretStr = SecretStr("")
    analyst_email: str = ""
    analyst_password: SecretStr = SecretStr("")

    # ---- platform limits ----
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "10/minute"
    max_request_mb: int = Field(default=11, ge=1, le=50)
    max_upload_mb: int = Field(default=10, ge=1, le=50)
    max_upload_rows: int = Field(default=100_000, ge=100, le=500_000)

    # ---- LLM / CrewAI ----
    llm_model: str = "gemini/gemini-3.5-flash-lite"
    llm_fallback_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    llm_base_url: str = ""
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=45, ge=5, le=600)
    llm_max_rpm: int = Field(default=30, ge=1, le=1000)
    max_llm_calls_per_analysis: int = Field(default=60, ge=6, le=200)

    # ---- Worker ----
    analysis_timeout_seconds: int = Field(default=900, ge=30, le=3600)
    worker_poll_seconds: float = Field(default=2.0, ge=0.2, le=60.0)

    @field_validator("database_url", "database_url_unpooled", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+psycopg://" + value.removeprefix("postgres://")
            if value.startswith("postgresql://"):
                return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _require_strong_secret_in_production(self) -> "Settings":
        if self.app_env == "production":
            if len(self.jwt_secret.get_secret_value()) < 32:
                raise ValueError("JWT_SECRET must be set (>= 32 chars) in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_request_bytes(self) -> int:
        return self.max_request_mb * 1024 * 1024

    @property
    def migration_url(self) -> str:
        """Neon best practice: use direct (unpooled) connection URL for Alembic schema migrations."""
        return self.database_url_unpooled or self.database_url

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.get_secret_value())

    def is_origin_allowed(self, origin: str) -> bool:
        if origin in self.cors_origins:
            return True
        return bool(self.cors_origin_regex and re.match(self.cors_origin_regex, origin))


@lru_cache
def get_settings() -> Settings:
    return Settings()
