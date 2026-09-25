"""Database connection management."""

import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# SQL schema for database initialization
SCHEMA = """
-- Daily usage aggregates
CREATE TABLE IF NOT EXISTS daily_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    usage_litres REAL NOT NULL,
    meter_reading REAL,
    is_estimated BOOLEAN DEFAULT FALSE,
    hourly_sum REAL,
    verified BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'scraper',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Hourly usage granular data
CREATE TABLE IF NOT EXISTS hourly_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    hour INTEGER NOT NULL,
    usage_litres REAL NOT NULL,
    meter_reading REAL,
    is_estimated BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'scraper',
    created_at TEXT NOT NULL,
    UNIQUE(date, hour)
);

-- Data synchronization log
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,
    source TEXT DEFAULT 'scraper',
    sync_time TEXT NOT NULL,
    status TEXT NOT NULL,
    records_fetched INTEGER DEFAULT 0,
    records_stored INTEGER DEFAULT 0,
    date_range_start TEXT,
    date_range_end TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    duration_seconds REAL,
    created_at TEXT NOT NULL
);

-- Alert history
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    alert_date TEXT NOT NULL,
    message TEXT NOT NULL,
    value REAL,
    threshold REAL,
    notified BOOLEAN DEFAULT FALSE,
    notified_at TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TEXT,
    created_at TEXT NOT NULL
);

-- Configuration/settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_usage(date);
CREATE INDEX IF NOT EXISTS idx_hourly_usage_date ON hourly_usage(date);
CREATE INDEX IF NOT EXISTS idx_hourly_usage_date_hour ON hourly_usage(date, hour);
CREATE INDEX IF NOT EXISTS idx_sync_log_type ON sync_log(sync_type);
CREATE INDEX IF NOT EXISTS idx_sync_log_time ON sync_log(sync_time);
CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts(alert_date);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_notified ON alerts(notified);
"""


class Database:
    """Async SQLite database manager."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._connection: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        return self.settings.db_path

    async def connect(self) -> None:
        """Initialize database connection and create schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys = ON")

        # Create schema
        await self._connection.executescript(SCHEMA)
        columns = await self._connection.execute_fetchall("PRAGMA table_info(sync_log)")
        if "source" not in {column[1] for column in columns}:
            await self._connection.execute(
                "ALTER TABLE sync_log ADD COLUMN source TEXT DEFAULT 'scraper'"
            )
        await self._connection.commit()

        logger.info(f"Database connected: {self.db_path}")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database disconnected")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get database connection context manager."""
        if not self._connection:
            await self.connect()
        yield self._connection  # type: ignore

    async def execute(
        self,
        query: str,
        parameters: tuple | dict | None = None
    ) -> aiosqlite.Cursor:
        """Execute a query and return cursor."""
        async with self.get_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            await conn.commit()
            return cursor

    async def fetch_one(
        self,
        query: str,
        parameters: tuple | dict | None = None
    ) -> dict | None:
        """Fetch a single row."""
        async with self.get_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(
        self,
        query: str,
        parameters: tuple | dict | None = None
    ) -> list[dict]:
        """Fetch all rows."""
        async with self.get_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Singleton database instance
_db: Database | None = None


def get_database() -> Database:
    """Get singleton database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
