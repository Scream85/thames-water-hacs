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

    # Thames Water credentials
    thames_water_email: str = Field(description="Thames Water login email")
    thames_water_password: str = Field(description="Thames Water login password")

    # API authentication
    thames_water_api_key: str = Field(description="API key for authentication")

    # Alert configuration
    spike_threshold: int = Field(default=800, description="Usage threshold for alerts (litres)")
    notification_email: str = Field(
        default="",
        description="Email address for notifications"
    )

    # Service URL for email links
    service_url: str = Field(
        default="http://localhost:8096",
        description="Public URL of the service for email links"
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

    # Scraper configuration
    scraper_headless: bool = Field(
        default=True,
        description="Run Chrome in headless mode"
    )
    scraper_timeout: int = Field(
        default=30,
        description="Selenium wait timeout in seconds"
    )

    # Scheduler configuration
    daily_fetch_hour: int = Field(
        default=6,
        description="Hour to run daily fetch (0-23)"
    )
    daily_fetch_minute: int = Field(
        default=0,
        description="Minute to run daily fetch (0-59)"
    )
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
