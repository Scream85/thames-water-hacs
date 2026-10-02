"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API authentication
    thames_water_api_key: str = Field(description="API key for authentication")
    ingest_api_key: str | None = Field(
        default=None,
        description="Shared key accepted from the Hands ingest adapter",
    )

    # Alert configuration
    spike_threshold: int = Field(default=800, description="Usage threshold for alerts (litres)")
    notification_email: str = Field(
        default="gavin@slaters.uk.com",
        description="Email address for notifications"
    )

    # Service configuration
    port: int = Field(default=8096, description="Service port")
    log_level: Literal["debug", "info", "warning", "error"] = Field(
        default="info",
        description="Logging level"
    )
    db_path: Path = Field(
        default=Path("data/thames_water.db"),
        description="Path to SQLite database"
    )

    # SMTP configuration for email notifications
    smtp_host: str | None = Field(
        default=None,
        description="SMTP server hostname"
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port"
    )
    smtp_username: str | None = Field(
        default=None,
        description="SMTP username"
    )
    smtp_password: str | None = Field(
        default=None,
        description="SMTP password"
    )
    smtp_from: str | None = Field(
        default=None,
        description="From email address"
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection"
    )

    # Gmail MCP integration
    gmail_mcp_enabled: bool = Field(
        default=False,
        description="Whether Gmail MCP is available for notifications"
    )

    # Scheduler configuration
    weekly_verify_day: str = Field(
        default="sun",
        description="Day of week for weekly verification"
    )
    weekly_verify_hour: int = Field(
        default=7,
        description="Hour to run weekly verification"
    )

    @property
    def database_url(self) -> str:
        """SQLite database URL for async connection."""
        return f"sqlite+aiosqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
