"""
Application configuration — all settings from environment variables.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ──────────────────────────────────────────────
    PORT: int = 8000
    ENVIRONMENT: str = "development"

    # ── Database ────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://arena:arena@localhost:5432/arena"

    # ── Redis ───────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Auth ────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── CORS ────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── Market Data ─────────────────────────────────────────
    POLYGON_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = "demo"

    # ── AI Agent LLMs ───────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # ── OAuth ───────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── Arena Config ────────────────────────────────────────
    SIGNUP_TOKEN_BONUS: int = 5000
    DAILY_LOGIN_BONUS: int = 100
    PLATFORM_FEE_RATE: float = 0.05  # 5% of daily pot
    PAPER_TRADE_SLIPPAGE: float = 0.001  # 0.1%
    AGENT_STARTING_CAPITAL: float = 100_000.0
    MARKET_CLOSE_UTC: str = "21:05"  # 16:05 ET
    AGENT_TRADE_INTERVAL: int = 60   # seconds
    LEADERBOARD_UPDATE_INTERVAL: int = 10  # seconds

    # ── Admin ───────────────────────────────────────────────
    ADMIN_EMAIL: str = "admin@arena.local"
    ADMIN_PASSWORD: str = "change-me"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def async_database_url(self) -> str:
        """Convert postgres:// to postgresql+asyncpg:// for async SQLAlchemy."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if "postgresql://" in url and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # Remove asyncpg if present
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url


settings = Settings()
