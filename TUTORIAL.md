# Thames Water Monitoring Service: A Complete Tutorial

*A step-by-step guide to understanding this Python codebase*

> **Historical (v1).** This tutorial walks the Selenium-era design tagged `v1-selenium`. From v2.0.0 collection moved to hands, and v2.1.0 removed the scraper, its settings and the backfill scripts from this tree.

---

## Table of Contents

1. [The Big Picture](#lesson-1-the-big-picture)
2. [Architecture Overview](#lesson-2-architecture-overview)
3. [How the Application Starts](#lesson-3-how-the-application-starts)
4. [Configuration: The Control Panel](#lesson-4-configuration)
5. [Data Models: The Blueprints](#lesson-5-data-models)
6. [The Database Layer](#lesson-6-the-database-layer)
7. [The Scraper: Where the Magic Happens](#lesson-7-the-scraper)
8. [Scheduled Jobs: The Automation Engine](#lesson-8-scheduled-jobs)
9. [The API: Opening the Door to the Outside](#lesson-9-the-api)
10. [The Dashboard: Making Data Visual](#lesson-10-the-dashboard)
11. [Putting It All Together](#lesson-11-putting-it-all-together)

---

## Lesson 1: The Big Picture

### What Does This Code Actually Do?

Imagine you have a water meter in your house. Thames Water reads it and sends you a bill every six months. But what if you could see your water usage *every single day* — or even *every hour*? What if you could get an alert when your usage spikes (maybe there's a leak)?

> **Note:** Thames Water's data has a ~3 day lag, so you're seeing usage from a few days ago rather than real-time. Still far better than waiting 6 months for a bill!

That's exactly what this code does.

**The problem it solves:**
- Thames Water has a website where you can see your water usage, but it's clunky and you have to manually log in
- You only get a bill every 6 months, so problems go unnoticed
- There's no way to get alerts when something unusual happens

**The solution:**
This service automatically:
1. **Logs into Thames Water's website** every morning at 6am (like a robot doing your browsing for you)
2. **Extracts your water usage data** (how much water you used each day and each hour)
3. **Stores it in a database** so you have a permanent record
4. **Provides a dashboard** where you can see charts and trends
5. **Sends you email alerts** if your usage exceeds a threshold (like 800 litres per day)

### A Real-World Analogy

Think of this service like having a personal assistant who:
- Wakes up at 6am every day
- Logs into your Thames Water account
- Writes down all your water usage in a notebook
- Creates nice charts for you to look at
- Texts you if something looks wrong

The "notebook" is a database. The "charts" are a web dashboard. The "texting" is email alerts.

### Comprehension Check

Before moving on, you should be able to answer:
1. What website does this service interact with?
2. What are the three main things the service does with the data it collects?
3. Why is this useful compared to just logging into Thames Water yourself?

---

## Lesson 2: Architecture Overview

### The Building Blocks

This service is made up of several **modules** (think of them as departments in a company). Each module has a specific job:

```
thames-water-service/
├── src/                      # All the Python code lives here
│   ├── main.py              # The "front door" - starts everything
│   ├── config.py            # Settings and configuration
│   │
│   ├── api/                 # The "customer service desk"
│   │   ├── routes.py        # Defines what URLs are available
│   │   ├── schemas.py       # Defines the shape of API responses
│   │   └── middleware.py    # Security (API key checking)
│   │
│   ├── database/            # The "filing cabinet"
│   │   ├── connection.py    # How to connect to the database
│   │   ├── models.py        # Blueprints for our data
│   │   └── queries.py       # How to read/write data
│   │
│   ├── scraper/             # The "field agent" that visits Thames Water
│   │   ├── extractor.py     # The main scraping logic
│   │   ├── parser.py        # Makes sense of the data
│   │   └── exceptions.py    # What can go wrong
│   │
│   ├── scheduler/           # The "alarm clock"
│   │   ├── manager.py       # Manages scheduled tasks
│   │   └── jobs.py          # The actual tasks to run
│   │
│   ├── notifications/       # The "messenger"
│   │   └── email.py         # Sends alert emails
│   │
│   └── utils/               # Helpful tools used everywhere
│       ├── logger.py        # Keeps a record of what happened
│       └── retry.py         # Tries again if something fails
│
├── static/                   # The dashboard (HTML, CSS, JavaScript)
│   ├── index.html           # The main dashboard page
│   ├── js/dashboard.js      # Chart logic and interactivity
│   └── css/styles.css       # How it looks
│
└── data/                     # Where the database file lives
    └── thames_water.db      # The actual database
```

### How They Connect (The Flow)

Here's how data flows through the system:

```
┌─────────────────────────────────────────────────────────────────┐
│                         SCHEDULER                               │
│                    (Wakes up at 6am)                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SCRAPER                                 │
│    (Logs into Thames Water, navigates pages, grabs data)        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATABASE                                 │
│              (Stores all the water usage data)                  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│       API        │            │   NOTIFICATIONS  │
│ (Dashboard data) │            │  (Alert emails)  │
└──────────────────┘            └──────────────────┘
```

### A Company Analogy

Think of this as a small company:

| Module | Role | What They Do |
|--------|------|--------------|
| **Scheduler** | The Manager | Decides when work should happen |
| **Scraper** | The Field Agent | Goes out and collects information |
| **Database** | The Archivist | Stores and organizes all records |
| **API** | Customer Service | Answers questions from the outside world |
| **Notifications** | The Messenger | Delivers urgent news |
| **Config** | HR/Admin | Knows all the passwords and settings |

### Comprehension Check

1. If you wanted to change how often data is collected, which module would you look at?
2. If the dashboard is showing wrong data, which modules might be involved?
3. What's the difference between the `scraper` and the `api` modules?

---

## Lesson 3: How the Application Starts

### The Entry Point: `main.py`

When you start any program, there's always a "front door" — the first piece of code that runs. In this service, that's `src/main.py`.

Let me walk you through it:

```python
"""Thames Water Monitoring Service - FastAPI Application."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.routes import router
from src.config import get_settings
from src.database.connection import get_database
from src.utils.logger import setup_logging, get_logger
```

**What's happening here:**

```python
# These lines are "imports" - like gathering tools before starting work
# Each import brings in code that someone else wrote so we don't have to

from fastapi import FastAPI       # FastAPI is a framework for building web APIs
                                  # Think of it as a pre-built restaurant kitchen
                                  # You just need to decide what dishes to make

from src.api.routes import router # This brings in our API endpoints (more on this later)
from src.config import get_settings # This brings in our configuration
from src.database.connection import get_database # This brings in our database connection
```

### The Lifespan Manager: Startup and Shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Thames Water Monitoring Service")

    # Initialize database
    db = get_database()
    await db.connect()
    logger.info("Database connected")

    # Start scheduler
    try:
        from src.scheduler.manager import start_scheduler
        await start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning(f"Could not start scheduler: {e}")

    yield  # <-- This is where the app runs

    # Shutdown
    logger.info("Shutting down Thames Water Monitoring Service")
    await db.disconnect()
```

**What's happening here:**

Think of this like opening and closing a restaurant:

1. **Before `yield`** = Opening procedures (turn on lights, prep kitchen, start coffee)
   - Connect to the database
   - Start the scheduler (the alarm clock that triggers jobs)

2. **`yield`** = The restaurant is open for business

3. **After `yield`** = Closing procedures (clean up, turn off equipment)
   - Disconnect from the database

The `@asynccontextmanager` decorator is Python's way of saying "this function manages a resource that needs setup and cleanup."

### Creating the FastAPI Application

```python
# Create FastAPI app
app = FastAPI(
    title="Thames Water Monitoring Service",
    description="Automated water usage monitoring with REST API and dashboard",
    version="1.0.0",
    lifespan=lifespan,  # Use our startup/shutdown manager
)

# Add CORS middleware (allows the dashboard to talk to the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount static files for dashboard
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")
```

**What's happening here:**

```python
app = FastAPI(...)  # Create the application with some metadata
                    # Like naming your restaurant and writing the sign

app.add_middleware(CORSMiddleware, ...)  # Security settings
                                         # Like deciding who's allowed in

app.include_router(router)  # Add all our API endpoints
                           # Like adding all the menu items

app.mount("/static", ...)  # Make the static folder (HTML, CSS, JS) available
                          # Like setting up the dining area
```

### The Dashboard Route

```python
@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the dashboard HTML."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Thames Water Monitoring Service", "docs": "/docs"}
```

This says: "When someone visits the root URL (`/`), show them the dashboard."

### Comprehension Check

1. What are the two things that happen when the application starts up?
2. What does `yield` do in the lifespan function?
3. If you visit `https://water.gavinslater.co.uk/`, which function handles that request?

---

---

## Lesson 4: Configuration

### Why Configuration Matters

Every application needs settings: passwords, email addresses, thresholds, ports, and so on. You could hardcode these directly in your code:

```python
# BAD: Hardcoded values
email = "gavin@example.com"
password = "secret123"
```

But this is problematic:
- **Security risk**: Passwords end up in your code repository
- **Inflexibility**: Changing a setting means changing code
- **Environment differences**: Your laptop uses different settings than your server

The solution is **environment variables** — settings that live *outside* your code, in the operating system or in a `.env` file.

### The Config File: `src/config.py`

This file defines all the settings the application needs. Let's walk through it:

```python
"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
```

**What's happening here:**

- `pydantic` is a library for data validation — it ensures your data is the right type
- `pydantic_settings` extends this to read from environment variables
- `lru_cache` is a performance optimization (we'll explain below)

### The Settings Class

```python
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",           # Read from a .env file
        env_file_encoding="utf-8", # Handle special characters
        case_sensitive=False,      # EMAIL and email are the same
        extra="ignore",            # Ignore unknown variables
    )

    # Thames Water credentials
    thames_water_email: str = Field(description="Thames Water login email")
    thames_water_password: str = Field(description="Thames Water login password")

    # API authentication
    thames_water_api_key: str = Field(description="API key for authentication")

    # Alert configuration
    spike_threshold: int = Field(default=800, description="Usage threshold for alerts (litres)")
```

**What's happening here:**

Think of this class as a **form** that defines what information we need:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `thames_water_email` | string | (required) | Login email for Thames Water |
| `thames_water_password` | string | (required) | Login password |
| `spike_threshold` | integer | 800 | Alert if daily usage exceeds this |

The `Field(default=800)` means "if not provided, use 800". Fields without defaults are required.

### How Environment Variables Work

When the app starts, Pydantic automatically:

1. Looks for a `.env` file in the project root
2. Reads environment variables from the operating system
3. Maps them to the Settings fields (case-insensitive)

For example, if your `.env` file contains:

```bash
THAMES_WATER_EMAIL=gavin@example.com
THAMES_WATER_PASSWORD=mysecretpassword
SPIKE_THRESHOLD=1000
```

Then `settings.thames_water_email` will be `"gavin@example.com"` and `settings.spike_threshold` will be `1000`.

### The Full Settings Class

Here are all the settings the application uses:

```python
class Settings(BaseSettings):
    # Thames Water credentials
    thames_water_email: str
    thames_water_password: str
    thames_water_api_key: str

    # Alert configuration
    spike_threshold: int = 800                    # Litres per day
    notification_email: str = "gavin@slaters.uk.com"

    # Service configuration
    port: int = 8096                              # Which port to run on
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    db_path: Path = Path("data/thames_water.db")  # Where to store the database

    # SMTP for email notifications
    smtp_host: str | None = None                  # Optional email server
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None

    # Scraper configuration
    scraper_headless: bool = True                 # Run browser invisibly
    scraper_timeout: int = 30                     # Seconds to wait for pages

    # Scheduler configuration
    daily_fetch_hour: int = 6                     # Run at 6 AM
    daily_fetch_minute: int = 0
    weekly_verify_day: str = "sun"                # Run on Sundays
    weekly_verify_hour: int = 7                   # At 7 AM
```

### Type Hints Explained

You'll notice things like `str`, `int`, `bool`, `str | None`. These are **type hints**:

| Type Hint | Meaning | Example Values |
|-----------|---------|----------------|
| `str` | Text | `"hello"`, `"gavin@example.com"` |
| `int` | Whole number | `800`, `6`, `8096` |
| `bool` | True or False | `True`, `False` |
| `Path` | A file/folder path | `Path("data/thames_water.db")` |
| `str \| None` | Text OR nothing | `"smtp.gmail.com"` or `None` |
| `Literal["a", "b"]` | One of these specific values | `"debug"` or `"info"` |

The `str | None` syntax (called a "union type") means "this can be a string OR it can be empty (None)". This is useful for optional settings like SMTP configuration.

### The get_settings() Function

```python
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

**What's happening here:**

1. `Settings()` creates a new Settings object, reading from environment variables
2. `@lru_cache` is a **decorator** that remembers the result

The `@lru_cache` decorator is a performance optimization. Without it, every time you call `get_settings()`, Python would:
- Read the `.env` file
- Parse all the variables
- Create a new Settings object

With `@lru_cache`, it does this once and remembers the answer. Think of it like a waiter who writes down your order rather than asking you to repeat it every time they walk past.

### How Other Code Uses Settings

Throughout the codebase, you'll see:

```python
from src.config import get_settings

settings = get_settings()

# Now you can access any setting
if usage > settings.spike_threshold:
    send_alert()
```

This pattern keeps configuration centralized — if you need to change the spike threshold, you change it in one place (the `.env` file or environment variable), not scattered throughout the code.

### Real-World Analogy

Think of the Settings class like the **control panel** of a machine:

- The `.env` file is like the instruction manual that came with the machine
- The Settings class defines what knobs and dials exist
- Default values are the factory settings
- Required fields (no default) are things you *must* configure before use

### Comprehension Check

1. Where does the application look for configuration values?
2. What happens if you don't provide a value for `thames_water_email`?
3. What happens if you don't provide a value for `spike_threshold`?
4. Why do we use `@lru_cache` on `get_settings()`?

---

## Lesson 5: Data Models

### What Are Models?

Before storing data, we need to define its **shape**. What information do we track? What type is each piece? Is it required or optional?

In Python, we use **classes** to define these shapes. The `pydantic` library makes this easy and adds automatic validation.

### The Models File: `src/database/models.py`

This file defines the "blueprints" for all the data we work with. Let's look at the main one:

### DailyUsage: Your Daily Water Record

```python
class DailyUsage(BaseModel):
    """Daily water usage record."""

    id: int | None = None
    date: str = Field(description="Date in YYYY-MM-DD format")
    usage_litres: float = Field(description="Total daily usage in litres")
    meter_reading: float | None = Field(default=None, description="End-of-day meter reading")
    is_estimated: bool = Field(default=False, description="Whether data is estimated")
    hourly_sum: float | None = Field(default=None, description="Sum of hourly data")
    verified: bool = Field(default=False, description="Whether hourly sum matches daily")
    source: str = Field(default="scraper", description="Data source")
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

**What each field means:**

| Field | Type | Purpose |
|-------|------|---------|
| `id` | int or None | Database row ID (assigned automatically) |
| `date` | str | The date, like "2025-12-17" |
| `usage_litres` | float | How much water used (e.g., 542.5) |
| `meter_reading` | float or None | The actual meter reading number (e.g., 931197) |
| `is_estimated` | bool | Thames Water sometimes estimates readings |
| `hourly_sum` | float or None | Sum of all hourly readings for verification |
| `verified` | bool | Does hourly sum match the daily total? |
| `source` | str | Where this data came from |
| `created_at` | datetime or None | When this record was created |

**Why `float` for usage?**

Water usage can have decimals (542.5 litres), so we use `float` (floating-point number) rather than `int` (integer/whole number).

**Why `meter_reading` is important:**

The meter reading is the cumulative number on your physical water meter. If yesterday it was 931,000 and today it's 931,500, you used 500 litres. This is the "source of truth" — more reliable than Thames Water's calculated daily figures.

### HourlyUsage: Granular Breakdown

```python
class HourlyUsage(BaseModel):
    """Hourly water usage record."""

    id: int | None = None
    date: str = Field(description="Date in YYYY-MM-DD format")
    hour: int = Field(ge=0, le=23, description="Hour of day (0-23)")
    usage_litres: float = Field(description="Hourly usage in litres")
    meter_reading: float | None = Field(default=None, description="Meter reading at hour end")
    is_estimated: bool = Field(default=False, description="Whether data is estimated")
    source: str = Field(default="scraper", description="Data source")
    created_at: datetime | None = None
```

**New concept: Validation constraints**

```python
hour: int = Field(ge=0, le=23, description="Hour of day (0-23)")
```

- `ge=0` means "greater than or equal to 0"
- `le=23` means "less than or equal to 23"

If you try to create an HourlyUsage with `hour=25`, Pydantic will raise an error. This catches bugs early.

### Alert: When Something's Wrong

```python
class Alert(BaseModel):
    """Alert record."""

    id: int | None = None
    alert_type: Literal["spike", "sync_error", "verification_mismatch", "data_unavailable", "data_available"]
    alert_date: str
    message: str
    value: float | None = None
    threshold: float | None = None
    notified: bool = False
    acknowledged: bool = False
    created_at: datetime | None = None
```

**The `Literal` type:**

```python
alert_type: Literal["spike", "sync_error", "verification_mismatch", "data_unavailable", "data_available"]
```

This says "alert_type can ONLY be one of these five strings". Try to set it to `"warning"` and Pydantic rejects it. This prevents typos and ensures consistency.

**Alert types explained:**
| Type | When It's Created |
|------|-------------------|
| `spike` | Daily usage exceeds 800L threshold |
| `sync_error` | Scraper failed to connect or extract data |
| `verification_mismatch` | Daily total doesn't match meter reading change |
| `data_unavailable` | Thames Water has no data available for a date |
| `data_available` | Data became available for a previously unavailable date |

### SyncLog: Keeping Track of Jobs

```python
class SyncLog(BaseModel):
    """Data synchronization log entry."""

    sync_type: Literal["daily", "hourly", "weekly_verify", "backfill"]
    sync_time: datetime
    status: Literal["success", "error", "partial"]
    records_fetched: int = 0
    records_stored: int = 0
    error_message: str | None = None
    duration_seconds: float | None = None
```

Every time the scraper runs, it creates a SyncLog entry. This lets you see:
- When did it run?
- Did it succeed or fail?
- How many records were collected?
- How long did it take?

### UsageSummary: Statistics

```python
class UsageSummary(BaseModel):
    """Usage summary statistics."""

    period: str                    # e.g., "30 days"
    total_litres: float           # Total water used
    average_daily: float          # Average per day
    max_daily: float              # Highest single day
    min_daily: float              # Lowest single day
    days_recorded: int            # How many days of data
    days_above_threshold: int     # Days that exceeded 800L
    trend: Literal["rising", "falling", "stable"]
```

This isn't stored in the database — it's calculated on-the-fly when requested. It provides a quick summary for the dashboard.

### Real-World Analogy

Think of these models like **forms** or **spreadsheet templates**:

- `DailyUsage` is like a row in a spreadsheet with columns for date, usage, meter reading, etc.
- Each model defines what columns exist and what type of data goes in each
- Pydantic is like a strict data entry clerk who rejects invalid submissions

### Comprehension Check

1. What's the difference between `float` and `int`?
2. Why would `meter_reading` be `None` sometimes?
3. What does `Field(ge=0, le=23)` do?
4. Name the four possible values for `alert_type`.

---

## Lesson 6: The Database Layer

### What Is a Database?

A database is just an organised way to store data permanently. When you close the application and reopen it, the data is still there.

This application uses **SQLite** — a simple database stored as a single file (`data/thames_water.db`). Unlike bigger databases (PostgreSQL, MySQL), SQLite doesn't need a separate server. It's perfect for personal projects.

### The Two Database Files

The database layer is split into two files:

| File | Purpose |
|------|---------|
| `connection.py` | How to connect to the database and set it up |
| `queries.py` | How to read and write specific data |

Think of it like a library:
- `connection.py` is the building itself (opening hours, where to find things)
- `queries.py` is the librarian who knows how to find specific books

### Database Connection: `src/database/connection.py`

#### The Schema (Database Structure)

First, the file defines what **tables** exist in the database:

```python
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
"""
```

**This is SQL** (Structured Query Language) — the language databases understand.

**Breaking down the syntax:**

```sql
CREATE TABLE IF NOT EXISTS daily_usage (
```
- `CREATE TABLE` — make a new table
- `IF NOT EXISTS` — only if it doesn't already exist (prevents errors on restart)
- `daily_usage` — the table name

```sql
    id INTEGER PRIMARY KEY AUTOINCREMENT,
```
- `id` — column name
- `INTEGER` — stores whole numbers
- `PRIMARY KEY` — this column uniquely identifies each row
- `AUTOINCREMENT` — automatically assigns 1, 2, 3... to new rows

```sql
    date TEXT UNIQUE NOT NULL,
```
- `TEXT` — stores text (strings)
- `UNIQUE` — no two rows can have the same date
- `NOT NULL` — this field is required (can't be empty)

```sql
    meter_reading REAL,
```
- `REAL` — stores decimal numbers (like Python's `float`)
- No `NOT NULL` means this can be empty (optional)

```sql
    is_estimated BOOLEAN DEFAULT FALSE,
```
- `BOOLEAN` — true or false
- `DEFAULT FALSE` — if not specified, assume false

#### The Database Class

```python
class Database:
    """Async SQLite database manager."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._connection: aiosqlite.Connection | None = None
```

**What's happening:**

- `__init__` is called when you create a new Database object
- It loads settings and prepares a space to store the database connection
- `_connection` starts as `None` (not connected yet)

The underscore prefix (`_connection`) is a Python convention meaning "this is internal, don't access it directly from outside the class."

#### Connecting to the Database

```python
async def connect(self) -> None:
    """Initialize database connection and create schema."""
    # Ensure directory exists
    self.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to SQLite
    self._connection = await aiosqlite.connect(self.db_path)
    self._connection.row_factory = aiosqlite.Row

    # Create tables if they don't exist
    await self._connection.executescript(SCHEMA)
    await self._connection.commit()

    logger.info(f"Database connected: {self.db_path}")
```

**What's happening:**

1. `mkdir(parents=True, exist_ok=True)` — create the `data/` folder if it doesn't exist
2. `await aiosqlite.connect(...)` — open the database file
3. `row_factory = aiosqlite.Row` — return results as dictionaries (easier to work with)
4. `executescript(SCHEMA)` — run all the CREATE TABLE statements
5. `commit()` — save changes

**Why `async` and `await`?**

These keywords enable **asynchronous programming**. Here's an analogy:

**Synchronous (blocking):** You're at a coffee shop. You order, then stand and wait until your coffee is ready. Nothing else happens.

**Asynchronous (non-blocking):** You order, get a buzzer, sit down and read the news. When the buzzer goes off, you collect your coffee.

Database operations are slow (reading from disk). With `async`/`await`, Python can do other things while waiting for the database, making the application more responsive.

#### Running Queries

```python
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
```

This runs any SQL query. The `parameters` let you safely insert values:

```python
# DANGEROUS - SQL injection risk:
query = f"SELECT * FROM daily_usage WHERE date = '{user_input}'"

# SAFE - parameters are escaped:
query = "SELECT * FROM daily_usage WHERE date = ?"
parameters = (user_input,)
```

#### Fetching Data

```python
async def fetch_one(self, query: str, parameters=None) -> dict | None:
    """Fetch a single row."""
    cursor = await conn.execute(query, parameters)
    row = await cursor.fetchone()
    return dict(row) if row else None

async def fetch_all(self, query: str, parameters=None) -> list[dict]:
    """Fetch all rows."""
    cursor = await conn.execute(query, parameters)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
```

- `fetch_one` — get one row (or None if not found)
- `fetch_all` — get all matching rows as a list

#### The Singleton Pattern

```python
_db: Database | None = None

def get_database() -> Database:
    """Get singleton database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
```

This ensures there's only **one** Database instance for the whole application. The first call creates it; subsequent calls return the same one.

Think of it like a company having one filing cabinet, not one per employee.

### Database Queries: `src/database/queries.py`

This file contains functions for specific operations. Let's look at the key ones:

#### Inserting Daily Usage

```python
async def insert_daily_usage(usage: DailyUsage) -> int:
    """Insert or update daily usage record."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        """
        INSERT INTO daily_usage (date, usage_litres, meter_reading, ...)
        VALUES (?, ?, ?, ...)
        ON CONFLICT(date) DO UPDATE SET
            usage_litres = excluded.usage_litres,
            meter_reading = excluded.meter_reading,
            ...
        """,
        (usage.date, usage.usage_litres, usage.meter_reading, ...),
    )
```

**What's happening:**

This is an "upsert" — insert if new, update if exists:

1. `INSERT INTO daily_usage ... VALUES (?, ?, ?)` — try to insert a new row
2. `ON CONFLICT(date)` — if a row with this date already exists...
3. `DO UPDATE SET ...` — ...update it instead

The `?` placeholders are replaced with the tuple values in order. This prevents SQL injection attacks.

#### Getting Daily Usage

```python
async def get_daily_usage(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get daily usage records with optional date range."""
    db = get_database()

    conditions = []
    params: list = []

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT * FROM daily_usage
        {where_clause}
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """
```

**What's happening:**

This function builds a SQL query dynamically:

- If `start_date="2025-12-01"` and `end_date="2025-12-17"`, it creates:
  ```sql
  SELECT * FROM daily_usage
  WHERE date >= '2025-12-01' AND date <= '2025-12-17'
  ORDER BY date DESC
  LIMIT 100
  ```

- If no dates are provided, it skips the WHERE clause entirely

This pattern is called **query building** — constructing SQL based on what filters the caller wants.

#### Getting Usage Summary (Aggregation)

```python
async def get_usage_summary(days: int = 30) -> UsageSummary:
    """Get usage summary for the specified number of days."""

    result = await db.fetch_one(
        """
        SELECT
            COUNT(*) as days_recorded,
            SUM(usage_litres) as total_litres,
            AVG(usage_litres) as average_daily,
            MAX(usage_litres) as max_daily,
            MIN(usage_litres) as min_daily
        FROM (
            SELECT * FROM daily_usage
            ORDER BY date DESC
            LIMIT ?
        )
        """,
        (days,),
    )
```

**What's happening:**

This uses SQL **aggregate functions**:

| Function | What It Does |
|----------|--------------|
| `COUNT(*)` | Count rows |
| `SUM(usage_litres)` | Add up all values |
| `AVG(usage_litres)` | Calculate average |
| `MAX(usage_litres)` | Find highest value |
| `MIN(usage_litres)` | Find lowest value |

The inner query `SELECT * FROM daily_usage ORDER BY date DESC LIMIT ?` gets the last N days, then the outer query calculates statistics on those rows.

#### Checking for Alerts

```python
async def alert_exists(alert_type: str, alert_date: str) -> bool:
    """Check if an alert already exists for a specific type and date."""
    db = get_database()
    result = await db.fetch_one(
        "SELECT id FROM alerts WHERE alert_type = ? AND alert_date = ?",
        (alert_type, alert_date),
    )
    return result is not None
```

This prevents duplicate alerts — before creating a spike alert for December 17th, we check if one already exists.

### The Data Flow

Here's how data moves through the database layer:

```
┌─────────────────────────────────────────────────────────────┐
│                     SCRAPER                                 │
│              Extracts data from Thames Water                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ DailyUsage objects
                          │ HourlyUsage objects
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    queries.py                               │
│              insert_daily_usage()                           │
│              insert_hourly_usage()                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ SQL INSERT statements
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   connection.py                             │
│                     execute()                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                thames_water.db                              │
│                   (SQLite file)                             │
└─────────────────────────────────────────────────────────────┘
```

And in reverse when the dashboard needs data:

```
Dashboard → API → queries.py (get_daily_usage) → connection.py → SQLite → Data returned
```

### Real-World Analogy

Think of the database like a **filing cabinet**:

- **Tables** are drawers (one for daily records, one for hourly, one for alerts)
- **Rows** are individual folders in each drawer
- **Columns** are the labels on each folder (date, usage, etc.)
- **connection.py** is the key to the cabinet
- **queries.py** is the filing clerk who knows how to find and file things

### Comprehension Check

1. What does `CREATE TABLE IF NOT EXISTS` do?
2. What's the difference between `fetch_one` and `fetch_all`?
3. Why do we use `?` placeholders instead of putting values directly in the SQL string?
4. What does `ON CONFLICT(date) DO UPDATE` achieve?

---

## Lesson 7: The Scraper

This is the heart of the system. The scraper is what makes everything else possible — it's the "field agent" that visits Thames Water's website, logs in with your credentials, navigates to the usage pages, and extracts your data.

### What Is Web Scraping?

Web scraping is the automated extraction of data from websites. Instead of a human clicking buttons and copying numbers, a program does it.

There are two main approaches:

| Approach | How It Works | Best For |
|----------|--------------|----------|
| **API calls** | Request data directly from a server | Sites with public APIs |
| **Browser automation** | Control a real browser like a robot | Sites without APIs, or with login requirements |

Thames Water doesn't offer a public API, and their website requires login with JavaScript-heavy pages. So we use **browser automation** with a tool called **Selenium**.

### What Is Selenium?

Selenium is a tool that controls a real web browser (Chrome, Firefox, etc.) programmatically. It can:

- Open URLs
- Click buttons
- Fill in forms
- Wait for pages to load
- Read content from the page
- Capture network traffic

Think of it like having a robot sit at your computer, move the mouse, and click things — except it's all happening invisibly in the background ("headless" mode).

### The Extractor File: `src/scraper/extractor.py`

This is the largest file in the codebase (~1,400 lines). Let's break it down into digestible pieces.

#### The Class Structure

```python
class ThamesWaterExtractor:
    """Extracts water usage data from Thames Water website."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.driver: webdriver.Chrome | None = None
```

The class has two main attributes:
- `settings` — configuration (credentials, timeouts, etc.)
- `driver` — the Selenium browser instance (starts as None)

#### Setting Up the Browser

```python
def _setup_driver(self) -> webdriver.Chrome:
    """Configure and create Chrome WebDriver."""
    options = webdriver.ChromeOptions()

    # Run invisibly (no window appears)
    if self.settings.scraper_headless:
        options.add_argument("--headless=new")

    # Required for running in Docker/Linux
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Enable performance logging (to capture network requests)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Create the browser
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)

    return driver
```

**What's happening:**

1. **Headless mode** — The browser runs invisibly. No window pops up. This is essential for running on a server.

2. **Sandbox disabled** — Required for running inside Docker containers (a security setting that conflicts with containerisation).

3. **Performance logging** — This is crucial. It tells Chrome to record all network requests, which we'll use later to capture the actual data.

4. **Timeouts** — How long to wait before giving up on slow pages.

**Real-world analogy:** Setting up the browser is like preparing your spy before a mission — giving them the right disguise (headless), equipment (logging), and instructions (timeouts).

#### Logging In

```python
def _login(self) -> bool:
    """Log in to Thames Water account."""
    logger.info("Navigating to login page")
    self.driver.get("https://www.thameswater.co.uk/login")

    # Wait for the email field to appear
    email_field = WebDriverWait(self.driver, 30).until(
        EC.presence_of_element_located((By.ID, "email"))
    )

    # Enter credentials
    email_field.send_keys(self.settings.thames_water_email)

    password_field = self.driver.find_element(By.ID, "password")
    password_field.send_keys(self.settings.thames_water_password)

    # Click the login button
    login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    login_button.click()

    # Wait for successful login (dashboard appears)
    WebDriverWait(self.driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard, .account-overview"))
    )

    logger.info("Successfully logged in")
    return True
```

**What's happening:**

1. `self.driver.get(url)` — Navigate to a URL (like typing in the address bar)

2. `WebDriverWait(...).until(...)` — Wait up to 30 seconds for something to appear. This is important because web pages load asynchronously — elements appear at different times.

3. `EC.presence_of_element_located((By.ID, "email"))` — "Wait until an element with ID 'email' exists"

4. `element.send_keys("text")` — Type text into a field (like pressing keys on the keyboard)

5. `element.click()` — Click on an element

**Element locators explained:**

| Locator | Example | What It Finds |
|---------|---------|---------------|
| `By.ID` | `"email"` | Element with `id="email"` |
| `By.CSS_SELECTOR` | `"button[type='submit']"` | Button with type="submit" |
| `By.TAG_NAME` | `"select"` | All `<select>` elements |
| `By.XPATH` | `"//div[@class='usage']"` | More complex patterns |

#### Navigating to the Water Usage Page

```python
def _navigate_to_water_use(self) -> bool:
    """Navigate to the water usage page."""
    logger.info("Navigating to water usage page")

    # Go directly to the usage URL
    self.driver.get("https://www.thameswater.co.uk/my-account/my-water-use")

    # Wait for usage content to load
    WebDriverWait(self.driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".water-usage, .usage-chart"))
    )

    # Additional wait for JavaScript to fully render
    time.sleep(3)

    return True
```

**Why the `time.sleep(3)`?**

Sometimes `WebDriverWait` says "the element exists!" but JavaScript is still loading data into it. A short sleep gives the page time to fully render. It's not elegant, but it's practical.

#### The Key Insight: Capturing Network Traffic

Here's where things get clever. Thames Water's website uses JavaScript to fetch data from their servers. Instead of trying to parse the HTML (which is messy), we **intercept the network requests** and read the raw data.

```python
def _extract_from_logs(self) -> list[dict]:
    """Extract data from Chrome performance logs."""
    logs = self.driver.get_log("performance")
    data_items = []

    for entry in logs:
        try:
            log_entry = json.loads(entry["message"])
            message = log_entry.get("message", {})

            # Look for network responses
            if message.get("method") == "Network.responseReceived":
                url = message.get("params", {}).get("response", {}).get("url", "")

                # Is this the data we want?
                if "getSmartWaterMeterConsumptions" in url:
                    # Get the response body
                    request_id = message["params"]["requestId"]
                    response = self.driver.execute_cdp_cmd(
                        "Network.getResponseBody",
                        {"requestId": request_id}
                    )
                    body = response.get("body", "")
                    data = json.loads(body)
                    data_items.append(data)

        except Exception:
            continue

    return data_items
```

**What's happening:**

1. `self.driver.get_log("performance")` — Get all recorded network activity

2. We loop through looking for `Network.responseReceived` events — these are completed HTTP responses

3. We filter for URLs containing `getSmartWaterMeterConsumptions` — this is Thames Water's internal API endpoint

4. `execute_cdp_cmd("Network.getResponseBody", ...)` — Ask Chrome for the actual response content

5. Parse the JSON response and collect it

**Real-world analogy:** Instead of reading a letter after it's been opened and scattered across a desk, we intercept it at the mailbox and read it directly. Cleaner and more reliable.

#### Selecting Dropdowns (UI-Based Approach)

Thames Water's page has dropdown menus to select different views:
- "Monthly (by days)" vs "Daily (by hours)"
- "Last 30 days" vs specific dates

Here's how we interact with them:

```python
def _extract_last_30_days(self) -> list[DailyUsage]:
    """Extract daily data using UI selection."""
    records = []

    # Find all dropdown elements on the page
    selects = self.driver.find_elements(By.TAG_NAME, "select")

    for sel in selects:
        try:
            select_obj = Select(sel)  # Selenium's helper for dropdowns
            options = [o.text for o in select_obj.options]

            # Look for the view type dropdown
            if "Monthly (by days)" in options:
                select_obj.select_by_visible_text("Monthly (by days)")
                logger.info("Selected 'Monthly (by days)' view")
                time.sleep(3)  # Wait for data to load
                break
        except Exception:
            continue

    # Now find and select the period dropdown
    selects = self.driver.find_elements(By.TAG_NAME, "select")
    for sel in selects:
        try:
            select_obj = Select(sel)
            options = [o.text for o in select_obj.options]

            if "Last 30 days" in options:
                select_obj.select_by_visible_text("Last 30 days")
                logger.info("Selected 'Last 30 days' period")
                time.sleep(5)  # Wait for data to load
                break
        except Exception:
            continue

    # Now extract the data from network logs
    raw_data = self._extract_from_logs()
    # ... parse and return records
```

**What's happening:**

1. `find_elements(By.TAG_NAME, "select")` — Find all `<select>` (dropdown) elements

2. `Select(sel)` — Wrap it in Selenium's Select helper class

3. `select_obj.options` — Get all options in the dropdown

4. `select_obj.select_by_visible_text("Last 30 days")` — Select by the text shown

5. Wait for the page to react, then capture the network response

**Why search all dropdowns?**

Thames Water's page doesn't have nice IDs on their dropdowns (like `id="view-type"`). So we search through all dropdowns, check what options they contain, and select from the right one.

#### Extracting Hourly Data

The hourly extraction follows a similar pattern:

```python
def _extract_latest_hourly(self) -> list[HourlyUsage]:
    """Extract hourly data for the latest available date."""
    records = []

    # Step 1: Select "Daily (by hours)" view
    selects = self.driver.find_elements(By.TAG_NAME, "select")
    for sel in selects:
        select_obj = Select(sel)
        options = [o.text for o in select_obj.options]

        if "Daily (by hours)" in options:
            select_obj.select_by_visible_text("Daily (by hours)")
            time.sleep(3)
            break

    # Step 2: Find date dropdown and select latest date
    selects = self.driver.find_elements(By.TAG_NAME, "select")
    for sel in selects:
        select_obj = Select(sel)
        options = [o.text for o in select_obj.options]

        # Look for date-like options (DD-MM-YYYY format)
        for opt in options:
            if re.match(r'^\d{1,2}-\d{1,2}-\d{4}', opt):
                latest_date_str = opt  # First one is the latest
                select_obj.select_by_visible_text(latest_date_str)
                time.sleep(5)
                break

    # Step 3: Extract from network logs
    raw_data = self._extract_from_logs()
    # ... parse hourly data
```

**Key difference:** The date dropdown contains dates in DD-MM-YYYY format (like "17-12-2025"), which we need to convert to YYYY-MM-DD format for storage.

#### Parsing the Data

Once we've captured the raw JSON from network logs, we need to parse it:

```python
def _parse_daily_data(self, raw_data: list[dict]) -> list[DailyUsage]:
    """Parse raw API data into DailyUsage records."""
    records = []

    for item in raw_data:
        if "Lines" not in item:
            continue

        for line in item["Lines"]:
            # Thames Water returns: Label, Usage, Read
            date_label = line.get("Label")  # e.g., "17 Dec"
            usage = line.get("Usage", 0)    # e.g., 542.5
            reading = line.get("Read")       # e.g., 931197

            # Convert "17 Dec" to "2025-12-17"
            date_str = self._parse_date_label(date_label)

            record = DailyUsage(
                date=date_str,
                usage_litres=float(usage),
                meter_reading=float(reading) if reading else None,
            )
            records.append(record)

    return records
```

**What's happening:**

Thames Water's API returns data like:
```json
{
  "Lines": [
    {"Label": "17 Dec", "Usage": 542.5, "Read": 931197},
    {"Label": "16 Dec", "Usage": 387.0, "Read": 930654},
    ...
  ]
}
```

We extract each line, convert the date format, and create `DailyUsage` objects.

#### The Main Entry Point

```python
def run_daily_sync(self) -> tuple[list[DailyUsage], list[HourlyUsage]]:
    """
    Run the daily sync to get latest data.

    Returns:
        Tuple of (daily_records, hourly_records)
    """
    try:
        # Set up browser
        self.driver = self._setup_driver()

        # Log in
        self._login()

        # Navigate to usage page
        self._navigate_to_water_use()

        # Extract daily data (last 30 days)
        daily_records = self._extract_last_30_days()

        # Extract hourly data (latest available date)
        hourly_records = self._extract_latest_hourly()

        return daily_records, hourly_records

    finally:
        # Always close the browser
        if self.driver:
            self.driver.quit()
```

**The `try`/`finally` pattern:**

The `finally` block runs no matter what — even if an error occurs. This ensures we always close the browser and don't leave zombie Chrome processes running.

### The Complete Flow

Here's how a daily sync works from start to finish:

```
1. Create Chrome browser (headless)
         │
         ▼
2. Navigate to Thames Water login page
         │
         ▼
3. Enter email and password
         │
         ▼
4. Click login button
         │
         ▼
5. Wait for dashboard to load
         │
         ▼
6. Navigate to "My Water Use" page
         │
         ▼
7. Select "Monthly (by days)" dropdown
         │
         ▼
8. Select "Last 30 days" period
         │
         ▼
9. Wait for data to load
         │
         ▼
10. Capture network logs → Extract JSON response
         │
         ▼
11. Parse JSON into DailyUsage objects
         │
         ▼
12. Select "Daily (by hours)" dropdown
         │
         ▼
13. Select latest available date
         │
         ▼
14. Capture network logs → Extract JSON response
         │
         ▼
15. Parse JSON into HourlyUsage objects
         │
         ▼
16. Close browser
         │
         ▼
17. Return (daily_records, hourly_records)
```

### Why This Approach?

You might wonder: why go through all this complexity?

**Option 1: Parse the HTML directly**
- Problem: HTML structure changes frequently, breaking scrapers
- Problem: Data might be loaded dynamically via JavaScript

**Option 2: Use Thames Water's API directly**
- Problem: No public API documentation
- Problem: Authentication cookies aren't passed through simple requests
- This is what we tried initially — it failed with "Permission denied"

**Option 3 (what we do): Browser automation + network capture**
- Browser handles all the JavaScript and authentication
- Network capture gives us clean, structured JSON
- More resilient to UI changes (we capture the data, not the display)

### Error Handling

The scraper has various try/except blocks to handle failures gracefully:

```python
try:
    select_obj.select_by_visible_text("Monthly (by days)")
except Exception:
    continue  # Try the next dropdown
```

Web scraping is inherently fragile — pages change, elements move, timing varies. Defensive coding with try/except prevents one failure from crashing the whole operation.

### Real-World Analogy

Imagine you're training someone to collect data from a website:

1. **Setup** — "Open Chrome and go to this website"
2. **Login** — "Type your email here, password there, click Login"
3. **Navigation** — "Click on 'My Water Use' in the menu"
4. **Selection** — "Find the dropdown that says 'Monthly', select it"
5. **Extraction** — "Don't try to read the chart — look at what the page is downloading from the server"
6. **Cleanup** — "Close the browser when done"

The scraper is just automating these exact steps.

### Comprehension Check

1. Why do we use "headless" mode for the browser?
2. What does `WebDriverWait(...).until(...)` do?
3. Why do we capture network logs instead of parsing the HTML?
4. What does the `finally` block ensure?
5. Why do we search through all `<select>` elements instead of finding one by ID?

---

## Lesson 8: Scheduled Jobs

Now we know how the scraper extracts data. But who triggers it? You don't want to manually run a script every morning. That's where **scheduled jobs** come in.

### What Is Job Scheduling?

Job scheduling is like setting an alarm clock for your code. You say "run this function every day at 6 AM" and the scheduler handles it.

This application uses **APScheduler** (Advanced Python Scheduler), a popular library for scheduling tasks in Python applications.

### The Two Scheduler Files

| File | Purpose |
|------|---------|
| `manager.py` | Sets up the scheduler and defines when jobs run |
| `jobs.py` | Defines what each job actually does |

Think of it like:
- `manager.py` is the calendar that says "meeting at 9 AM, lunch at 12 PM"
- `jobs.py` is the description of what happens in each meeting

### Scheduler Manager: `src/scheduler/manager.py`

#### Creating the Scheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None

def get_scheduler() -> AsyncIOScheduler:
    """Get or create scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler
```

**What's happening:**

- `AsyncIOScheduler` — A scheduler that works with Python's async/await
- We use the singleton pattern (like the database) — one scheduler for the whole app
- `global _scheduler` — Makes this variable accessible across function calls

#### Starting the Scheduler

```python
async def start_scheduler() -> None:
    """Start the scheduler with configured jobs."""
    settings = get_settings()
    scheduler = get_scheduler()

    if scheduler.running:
        logger.info("Scheduler already running")
        return

    # Import jobs here to avoid circular imports
    from src.scheduler.jobs import (
        daily_hourly_fetch_job,
        weekly_verification_job,
    )

    # Daily job: Fetch data at 6:00 AM
    scheduler.add_job(
        daily_hourly_fetch_job,           # The function to run
        CronTrigger(
            hour=settings.daily_fetch_hour,    # 6
            minute=settings.daily_fetch_minute, # 0
        ),
        id="daily_hourly_fetch",
        name="Fetch previous day hourly data",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace period
    )

    # Weekly job: Verify data on Sundays at 7:00 AM
    scheduler.add_job(
        weekly_verification_job,
        CronTrigger(
            day_of_week=settings.weekly_verify_day,  # "sun"
            hour=settings.weekly_verify_hour,         # 7
            minute=0,
        ),
        id="weekly_verification",
        name="Weekly data verification",
        replace_existing=True,
        misfire_grace_time=7200,  # 2 hour grace period
    )

    scheduler.start()
    logger.info("Scheduler started")
```

**What's happening:**

1. **Get the scheduler instance** and check if it's already running

2. **Import the job functions** — We import here (not at the top of the file) to avoid "circular imports" (where A imports B which imports A)

3. **Add jobs with `scheduler.add_job()`:**
   - First argument: the function to call
   - `CronTrigger`: when to run it (cron-style scheduling)
   - `id`: unique identifier for the job
   - `replace_existing=True`: if the job already exists, replace it
   - `misfire_grace_time`: if the job misses its scheduled time (e.g., server was down), still run it if within this window

4. **Start the scheduler** — It now runs in the background, checking the clock

#### Understanding Cron Triggers

Cron is a time-based scheduling syntax from Unix. `CronTrigger` uses similar concepts:

```python
CronTrigger(
    hour=6,
    minute=0,
)
```

This means "every day at 06:00".

```python
CronTrigger(
    day_of_week="sun",
    hour=7,
    minute=0,
)
```

This means "every Sunday at 07:00".

**Common cron patterns:**

| Pattern | Meaning |
|---------|---------|
| `hour=6, minute=0` | Daily at 6:00 AM |
| `hour=*/2` | Every 2 hours |
| `day_of_week="mon-fri", hour=9` | Weekdays at 9 AM |
| `day=1, hour=0` | First of each month at midnight |

#### Misfire Grace Time

```python
misfire_grace_time=3600  # 1 hour
```

What if the server was down at 6 AM? Without grace time, the job would simply be skipped.

With `misfire_grace_time=3600`, if the server comes back up at 6:45 AM, the scheduler says "this job was supposed to run at 6 AM, but we're still within the 1-hour grace period, so let's run it now."

#### Manually Triggering Jobs

```python
async def trigger_job(job_type: str, date: str | None = None) -> str:
    """Trigger a job manually."""
    from src.scheduler.jobs import (
        daily_hourly_fetch_job,
        weekly_verification_job,
        backfill_job,
    )

    job_id = str(uuid.uuid4())[:8]
    logger.info(f"Triggering manual job: {job_type}")

    if job_type == "daily":
        await daily_hourly_fetch_job()
    elif job_type == "weekly_verify":
        await weekly_verification_job()
    elif job_type == "backfill":
        await backfill_job()
    else:
        raise ValueError(f"Unknown job type: {job_type}")

    return job_id
```

This allows the API to trigger jobs on demand (useful for testing or catching up on missed data).

### Job Definitions: `src/scheduler/jobs.py`

This file defines what each scheduled job actually does.

#### The Daily Fetch Job

This is the main job that runs every morning:

```python
async def daily_hourly_fetch_job() -> None:
    """
    Daily job to fetch latest daily and hourly data.
    Runs at 6:00 AM daily.
    """
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Starting daily sync for {today}")

    # Create a log entry to track this sync
    sync_log = SyncLog(
        sync_type="daily",
        sync_time=datetime.now(timezone.utc),
        status="success",
    )

    try:
        # Run the scraper
        extractor = ThamesWaterExtractor()
        daily_records, hourly_records = extractor.run_daily_sync()

        # Store daily records (only new ones)
        daily_stored = 0
        for record in daily_records:
            existing = await get_daily_usage(
                start_date=record.date,
                end_date=record.date,
                limit=1
            )
            if not existing:
                await insert_daily_usage(record)
                daily_stored += 1
                await check_for_spike(record)  # Check if usage is too high

        # Store hourly records
        hourly_stored = 0
        for record in hourly_records:
            await insert_hourly_usage(record)
            hourly_stored += 1

        sync_log.records_fetched = len(daily_records) + len(hourly_records)
        sync_log.records_stored = daily_stored + hourly_stored

        logger.info(f"Daily sync complete: {daily_stored} daily, {hourly_stored} hourly")

    except Exception as e:
        sync_log.status = "error"
        sync_log.error_message = str(e)
        logger.error(f"Daily fetch failed: {e}")

        # Send error notification
        await send_error_notification(
            error_type="Daily Sync Failed",
            error_message=str(e),
        )

    finally:
        sync_log.duration_seconds = time.time() - start_time
        await create_sync_log(sync_log)
```

**What's happening step by step:**

1. **Start timing** — We record when the job started

2. **Create a sync log** — This will track the outcome (success/error, records count)

3. **Run the scraper** — Create an extractor and call `run_daily_sync()`

4. **Store daily records:**
   - Check if each record already exists (avoid duplicates)
   - If new, insert it and check for usage spikes

5. **Store hourly records** — Insert all hourly records (upsert handles duplicates)

6. **Handle errors** — If anything fails, log it and send a notification

7. **Record the sync** — Save the sync log to the database for auditing

#### Checking for Spikes

```python
async def check_for_spike(usage: DailyUsage) -> None:
    """Check if daily usage exceeds threshold and create alert."""
    settings = get_settings()
    threshold = settings.spike_threshold  # Default: 800L

    if usage.usage_litres > threshold:
        # Don't create duplicate alerts
        if await alert_exists("spike", usage.date):
            logger.debug(f"Spike alert already exists for {usage.date}")
            return

        logger.warning(f"Spike detected: {usage.usage_litres}L on {usage.date}")

        # Create alert record
        alert = Alert(
            alert_type="spike",
            alert_date=usage.date,
            message=f"Daily usage of {usage.usage_litres:.0f}L exceeded threshold of {threshold}L",
            value=usage.usage_litres,
            threshold=float(threshold),
        )
        alert_id = await create_alert(alert)

        # Send email notification
        try:
            await send_alert_email(
                subject=f"Thames Water Alert: High Usage on {usage.date}",
                body=f"""
Water usage spike detected!

Date: {usage.date}
Usage: {usage.usage_litres:.0f} litres
Threshold: {threshold} litres
Excess: {usage.usage_litres - threshold:.0f} litres

This could indicate:
- A leak or running tap
- Unusual household activity
- Irrigation system running too long

View details: https://water.gavinslater.co.uk
                """.strip(),
            )
            await mark_alert_notified(alert_id)
        except Exception as e:
            logger.error(f"Failed to send spike alert: {e}")
```

**What's happening:**

1. **Compare usage to threshold** — Is today's usage > 800L?

2. **Check for duplicates** — Don't create another alert if one already exists for this date

3. **Create an Alert record** — Store it in the database

4. **Send an email** — Notify you about the spike

5. **Mark as notified** — Update the alert so we know the email was sent

#### The Weekly Verification Job

This job checks data quality by comparing different data sources:

```python
async def weekly_verification_job() -> None:
    """
    Weekly job to verify data quality using meter readings.
    Runs every Sunday at 7:00 AM.
    """
    logger.info("Starting weekly verification")

    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    # Get daily records for the past week
    daily_records = await get_daily_usage(
        start_date=week_ago,
        end_date=today.strftime("%Y-%m-%d"),
    )

    for record in daily_records:
        date = record["date"]
        daily_usage = record["usage_litres"]

        # Get meter readings for this date
        meter_data = await get_meter_readings_for_date(date)

        if meter_data:
            meter_change = meter_data["meter_change"]

            # Does daily usage match meter change?
            diff = abs(daily_usage - meter_change)
            if diff <= 1:  # Within 1 litre tolerance
                # Verified!
                verified = True
            else:
                # Mismatch - create alert
                logger.warning(f"Verification mismatch for {date}")
                # ... create alert
```

**Why verify?**

Thames Water sometimes allocates usage inconsistently between days (especially overnight usage). The meter reading is the "source of truth" — the physical number on the meter.

This job catches discrepancies so you know if the data can be trusted.

### The Job Lifecycle

Here's how everything fits together:

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION STARTS                       │
│                      (main.py)                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   start_scheduler()                         │
│              Registers jobs with APScheduler                │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│  Daily Job       │            │  Weekly Job      │
│  6:00 AM daily   │            │  Sunday 7:00 AM  │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│ daily_hourly_    │            │ weekly_          │
│ fetch_job()      │            │ verification_    │
│                  │            │ job()            │
│ 1. Run scraper   │            │                  │
│ 2. Store data    │            │ 1. Get records   │
│ 3. Check spikes  │            │ 2. Compare meter │
│ 4. Log sync      │            │ 3. Flag issues   │
└──────────────────┘            └──────────────────┘
```

### Real-World Analogy

Think of the scheduler like a **night manager** at a business:

- **manager.py** is the manager's schedule: "Check inventory at 6 AM, do weekly audit on Sunday"
- **jobs.py** is the procedure manual: "Here's HOW to check inventory, step by step"
- **APScheduler** is the alarm clock that wakes the manager at the right times
- **Misfire grace time** is like saying "if you oversleep by an hour, still do the task"

### Why 6 AM?

The job runs at 6 AM because:

1. **Data delay** — Thames Water's data has a ~3 day lag, so running early in the morning catches yesterday's data (which is really 3-days-ago's data)

2. **Low load** — Running overnight/early morning means less competition for system resources

3. **Retry time** — If something fails at 6 AM, there's time to notice and fix it before the next day

### Comprehension Check

1. What library handles job scheduling in this application?
2. What does `CronTrigger(hour=6, minute=0)` mean?
3. What happens if the server is down at 6 AM but comes back at 6:30 AM?
4. What are the two scheduled jobs and what does each do?
5. Why do we check for existing alerts before creating a new spike alert?

---

## Lesson 9: The API

The API is the "customer service desk" of the application. It provides a structured way for the dashboard (or any other tool) to request data.

### What Is a REST API?

**REST** (Representational State Transfer) is a standard way to build web APIs. It uses:

- **URLs** to identify resources (e.g., `/api/usage/daily`)
- **HTTP methods** to specify actions (GET = read, POST = create)
- **JSON** to format data

When you visit the dashboard, JavaScript code makes requests like:
```
GET https://water.gavinslater.co.uk/api/usage/daily
```

And receives JSON data:
```json
[
  {"date": "2025-12-17", "usage_litres": 542.5},
  {"date": "2025-12-16", "usage_litres": 387.0}
]
```

### FastAPI: The Web Framework

This application uses **FastAPI**, a modern Python web framework. FastAPI is popular because it:

- Is fast (built on async Python)
- Automatically generates API documentation
- Validates request/response data using Pydantic
- Is easy to learn

### The Routes File: `src/api/routes.py`

This file defines all the API endpoints.

#### Creating the Router

```python
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api", tags=["usage"])
```

**What's happening:**

- `APIRouter()` creates a group of related endpoints
- `prefix="/api"` means all routes start with `/api`
- `tags=["usage"]` groups them in the documentation

#### A Simple Endpoint: Health Check

```python
@router.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "Thames Water Monitoring",
        "version": "1.0.0"
    }
```

**What's happening:**

- `@router.get("/health")` — This function handles GET requests to `/api/health`
- The function returns a dictionary, which FastAPI automatically converts to JSON

**Try it:** Visit `https://water.gavinslater.co.uk/api/health` and you'll see this JSON response.

#### Getting Daily Usage Data

```python
@router.get("/usage/daily")
async def get_daily_usage_endpoint(
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records"),
):
    """Get daily water usage records."""
    records = await get_daily_usage(
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return {
        "success": True,
        "data": records,
        "count": len(records),
    }
```

**What's happening:**

1. `@router.get("/usage/daily")` — Handle GET requests to `/api/usage/daily`

2. **Query parameters** — The function arguments become URL parameters:
   ```
   /api/usage/daily?start_date=2025-12-01&limit=30
   ```

3. `Query(...)` — Defines validation and documentation:
   - `None` = optional (no default required)
   - `ge=1, le=1000` = must be between 1 and 1000
   - `description` = shows up in API docs

4. **Call the database** — `get_daily_usage()` fetches from SQLite

5. **Return a response** — Dictionary with success flag, data, and count

#### Getting Hourly Data

```python
@router.get("/usage/hourly")
async def get_hourly_usage_endpoint(
    date: str = Query(..., description="Date to get hourly data for (YYYY-MM-DD)"),
):
    """Get hourly water usage for a specific date."""
    records = await get_hourly_usage(date)

    if not records:
        return {
            "success": True,
            "data": [],
            "message": f"No hourly data available for {date}"
        }

    return {
        "success": True,
        "data": records,
        "count": len(records),
    }
```

**Key difference:** `Query(...)` with `...` (Ellipsis) means the parameter is **required**. The request will fail if `date` isn't provided.

#### Getting a Usage Summary

```python
@router.get("/usage/summary")
async def get_usage_summary_endpoint(
    days: int = Query(30, ge=1, le=365, description="Number of days to summarize"),
):
    """Get usage statistics summary."""
    summary = await get_usage_summary(days)
    return {
        "success": True,
        "data": summary.model_dump(),  # Convert Pydantic model to dict
    }
```

This endpoint calculates statistics (total, average, min, max) for the specified period.

#### Protected Endpoints: API Key Authentication

Some endpoints shouldn't be public. The sync trigger endpoint requires an API key:

```python
from fastapi import Header

async def verify_api_key(
    x_api_key: str = Header(..., description="API key for authentication")
) -> str:
    """Verify API key from request header."""
    settings = get_settings()
    if x_api_key != settings.thames_water_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return x_api_key


@router.post("/sync/trigger")
async def trigger_sync(
    sync_type: str = Query("daily", description="Type of sync to trigger"),
    api_key: str = Depends(verify_api_key),  # Requires valid API key
):
    """Manually trigger a data sync."""
    job_id = await trigger_job(sync_type)
    return {
        "success": True,
        "message": f"Sync triggered: {sync_type}",
        "job_id": job_id,
    }
```

**What's happening:**

1. `verify_api_key()` — A function that checks the `X-API-Key` header

2. `Header(...)` — Extracts a value from request headers

3. `HTTPException(status_code=401)` — Returns "Unauthorized" if key is wrong

4. `Depends(verify_api_key)` — FastAPI runs this check before the endpoint

**To call this endpoint:**
```bash
curl -X POST https://water.gavinslater.co.uk/api/sync/trigger \
  -H "X-API-Key: your-secret-key"
```

#### Getting Sync Status

```python
@router.get("/sync/status")
async def get_sync_status():
    """Get synchronization status."""
    last_daily = await get_last_sync("daily")
    last_weekly = await get_last_sync("weekly_verify")
    recent_errors = await get_recent_sync_errors(limit=5)

    return {
        "success": True,
        "data": {
            "last_daily_sync": last_daily["sync_time"] if last_daily else None,
            "last_daily_status": last_daily["status"] if last_daily else None,
            "last_weekly_verify": last_weekly["sync_time"] if last_weekly else None,
            "recent_errors": [
                {
                    "time": e["sync_time"],
                    "type": e["sync_type"],
                    "message": e["error_message"],
                }
                for e in recent_errors
            ],
        },
    }
```

This powers the monitoring — you can see when the last sync ran and if there were any errors.

#### Getting Alerts

```python
@router.get("/alerts")
async def get_alerts_endpoint(
    status: str = Query("all", description="Filter: all, unacknowledged, acknowledged"),
    limit: int = Query(20, ge=1, le=100),
):
    """Get alert history."""
    alerts = await get_alerts(status=status, limit=limit)
    return {
        "success": True,
        "data": alerts,
        "count": len(alerts),
    }
```

The dashboard uses this to show how many unacknowledged alerts exist.

### HTTP Methods Explained

| Method | Purpose | Example |
|--------|---------|---------|
| `GET` | Read data | Get daily usage |
| `POST` | Create/trigger something | Trigger a sync |
| `PUT` | Update existing data | (not used in this app) |
| `DELETE` | Remove data | (not used in this app) |

### Response Format

All endpoints follow a consistent format:

```json
{
  "success": true,
  "data": { ... },
  "count": 10,
  "message": "Optional message"
}
```

This makes it easy for the dashboard to handle responses consistently.

### Error Handling

When something goes wrong:

```python
@router.get("/usage/hourly")
async def get_hourly_usage_endpoint(date: str = Query(...)):
    try:
        records = await get_hourly_usage(date)
        return {"success": True, "data": records}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch hourly data: {str(e)}"
        )
```

`HTTPException` returns an error response:
```json
{
  "detail": "Failed to fetch hourly data: Database connection failed"
}
```

### Automatic API Documentation

One of FastAPI's best features: it automatically generates interactive documentation.

Visit `https://water.gavinslater.co.uk/docs` to see:

- List of all endpoints
- Expected parameters for each
- Try them out directly in the browser
- See example responses

This is generated from your code — the `description` parameters, type hints, and docstrings all contribute.

### How the Dashboard Uses the API

The dashboard (`static/js/dashboard.js`) makes fetch requests:

```javascript
// Fetch daily usage for the chart
async function loadDailyData(days) {
    const response = await fetch(`/api/usage/daily?limit=${days}`);
    const result = await response.json();

    if (result.success) {
        renderChart(result.data);
    }
}

// Fetch summary statistics
async function loadSummary() {
    const response = await fetch('/api/usage/summary?days=7');
    const result = await response.json();

    if (result.success) {
        updateCards(result.data);
    }
}
```

The flow:
```
User visits dashboard
       │
       ▼
Browser loads index.html
       │
       ▼
JavaScript runs, calls fetch('/api/usage/daily')
       │
       ▼
FastAPI receives request
       │
       ▼
routes.py calls get_daily_usage()
       │
       ▼
queries.py fetches from SQLite
       │
       ▼
Data returns as JSON
       │
       ▼
JavaScript renders charts
```

### The Complete API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | No | Service health check |
| `/api/usage/summary` | GET | No | Usage statistics |
| `/api/usage/daily` | GET | No | Daily usage records |
| `/api/usage/hourly` | GET | No | Hourly breakdown |
| `/api/usage/monthly` | GET | No | Monthly aggregates |
| `/api/alerts` | GET | No | Alert history |
| `/api/sync/status` | GET | No | Last sync info |
| `/api/sync/trigger` | POST | Yes | Trigger manual sync |

### Real-World Analogy

Think of the API like a **restaurant menu and ordering system**:

- **Endpoints** are menu items (what you can order)
- **Query parameters** are customisations ("medium rare", "no onions")
- **HTTP methods** are actions (GET = "what's available?", POST = "I'd like to order")
- **API key** is a VIP membership card (required for special requests)
- **JSON responses** are the dishes delivered to your table
- **API documentation** is the menu with descriptions and pictures

### Comprehension Check

1. What HTTP method would you use to read data?
2. What does `Query(None)` mean for a parameter?
3. What does `Query(...)` (with ellipsis) mean?
4. How does the sync trigger endpoint prevent unauthorised access?
5. Where can you find auto-generated API documentation?

---

## Lesson 10: The Dashboard

We've built a powerful backend that collects data, stores it, schedules jobs, and exposes an API. But how do users actually *see* this data? That's where the dashboard comes in — the visual face of our service.

### The Three Layers of a Web Frontend

The dashboard is built with three technologies that work together like a theatre production:

| Layer | Technology | Role | Theatre Analogy |
|-------|------------|------|-----------------|
| **Structure** | HTML | What elements exist and how they're organised | The stage and props |
| **Appearance** | CSS | How things look (colours, sizes, spacing) | Costumes and lighting |
| **Behaviour** | JavaScript | What happens when you interact | The actors performing |

These files live in the `static/` folder:
```
static/
├── index.html          # The structure
├── css/
│   └── styles.css      # The appearance
└── js/
    └── dashboard.js    # The behaviour
```

### Part 1: The HTML Structure

HTML (HyperText Markup Language) defines *what* is on the page. Open `static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thames Water Usage Dashboard</title>
    <link rel="stylesheet" href="/static/css/styles.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
</head>
```

**What's happening here:**
- `<head>` contains metadata and loads external resources
- `<link rel="stylesheet">` loads our CSS styling
- `<script src="...">` loads Chart.js (a charting library) from a CDN (Content Delivery Network)

The `<body>` contains the visible content, organised into **sections**:

```html
<body>
    <div class="container">
        <header>...</header>                    <!-- Title and status -->
        <section class="summary-cards">...</section>    <!-- Usage stats -->
        <section class="summary-cards cost-cards">...</section>  <!-- Cost stats -->
        <section class="chart-section">...</section>    <!-- Daily chart -->
        <section class="chart-section">...</section>    <!-- Hourly chart -->
        <section class="chart-section">...</section>    <!-- Monthly chart -->
        <section class="alerts-section">...</section>   <!-- Alert list -->
        <footer>...</footer>
    </div>
    <script src="/static/js/dashboard.js"></script>
</body>
```

**Key concept: Elements with IDs**

HTML elements can have `id` attributes that JavaScript uses to find and update them:

```html
<div class="card">
    <h3>Latest Day</h3>
    <div class="value" id="today-usage">--</div>
    <div class="unit">litres</div>
</div>
```

The `id="today-usage"` is like putting a name tag on this element. JavaScript will later find it and replace `--` with the actual usage number.

**Canvas elements for charts:**

```html
<canvas id="daily-chart"></canvas>
```

A `<canvas>` is a blank drawing surface. Chart.js will draw graphs on it.

### Part 2: CSS Styling

CSS (Cascading Style Sheets) defines *how* things look. Open `static/css/styles.css`:

**CSS Variables (Custom Properties):**

```css
:root {
    --primary-color: #0066cc;
    --secondary-color: #00a6ed;
    --success-color: #28a745;
    --warning-color: #ffc107;
    --danger-color: #dc3545;
    --background-color: #f5f7fa;
    --card-background: #ffffff;
    --text-color: #333333;
}
```

These are like **named paint colours**. Instead of writing `#0066cc` everywhere (hard to remember!), you write `var(--primary-color)`. If you want to change the primary colour throughout the entire site, you change it in one place.

**Styling Cards:**

```css
.card {
    background: var(--card-background);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    text-align: center;
}

.card .value {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--primary-color);
}
```

**What the CSS properties do:**
- `background` — the fill colour
- `border-radius: 12px` — rounded corners
- `padding: 20px` — space between content and edges
- `box-shadow` — subtle shadow for depth
- `font-size: 2.5rem` — text size (rem = relative to root font size)

**Responsive Design:**

```css
@media (max-width: 768px) {
    .summary-cards {
        grid-template-columns: repeat(2, 1fr);
    }
    .card .value {
        font-size: 2rem;
    }
}
```

This is a **media query**. It says: "If the screen is 768 pixels wide or less (like a tablet), apply these alternative styles." This makes the dashboard work on mobile devices.

### Part 3: JavaScript — The Engine

JavaScript makes the page *do things*. It fetches data from our API and renders it. Open `static/js/dashboard.js`:

**The Initialisation Pattern:**

```javascript
// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initDashboard);
```

This says: "When the page has finished loading its HTML structure, run the `initDashboard` function." We can't manipulate elements before they exist!

**The Main Initialisation Function:**

```javascript
async function initDashboard() {
    // Set default date for hourly picker (3 days ago due to data lag)
    const hourlyDatePicker = document.getElementById('hourly-date');
    const latestAvailable = new Date();
    latestAvailable.setDate(latestAvailable.getDate() - 3);
    hourlyDatePicker.value = latestAvailable.toISOString().split('T')[0];

    // Add event listeners
    setupEventListeners();

    // Load all data in parallel
    await Promise.all([
        checkHealth(),
        loadSummary(),
        loadDailyData(30),
        loadHourlyData(hourlyDatePicker.value),
        loadMonthlyData(),
        loadAlerts()
    ]);

    // Set up auto-refresh (every 5 minutes)
    setInterval(refreshData, 5 * 60 * 1000);
}
```

**Breaking this down:**

1. **Find the date picker** using `document.getElementById()` — this finds the HTML element with that ID
2. **Set a default date** 3 days ago (because Thames Water has a data lag)
3. **Set up event listeners** — things that happen when you click buttons
4. **Load data in parallel** — `Promise.all()` runs all these fetch operations simultaneously (faster than one-by-one)
5. **Set up auto-refresh** — `setInterval` runs a function every N milliseconds

### Fetching Data from the API

Here's how JavaScript talks to our Python API:

```javascript
async function loadSummary() {
    try {
        const response = await fetch(`${API_BASE}/api/usage/summary?days=7`);
        const data = await response.json();

        if (data.success) {
            const summary = data.data;
            document.getElementById('avg-usage').textContent =
                Math.round(summary.average_daily);
        }
    } catch (error) {
        console.error('Failed to load summary:', error);
    }
}
```

**Step by step:**

1. `fetch('/api/usage/summary?days=7')` — Makes an HTTP GET request to our API
2. `await response.json()` — Converts the response to a JavaScript object
3. `data.success` — Checks if the API returned success
4. `document.getElementById('avg-usage')` — Finds the HTML element
5. `.textContent = Math.round(...)` — Sets the text content to the rounded number

**The async/await pattern:**
- `async` marks a function that will do asynchronous work (like network requests)
- `await` pauses execution until the network request completes
- This makes asynchronous code read like synchronous code

### Cost Calculations

The dashboard calculates costs client-side using Thames Water's pricing:

```javascript
// Thames Water pricing (from Dec 2025 bill)
const PRICING = {
    ratePerLitre: 0.0040223,  // £4.0223 per m³ = £0.0040223 per litre
    dailyFixedCharge: 0.532   // (£31.37 + £63.86) / 179 days
};

function calculateCost(litres, includeDailyFixed = true) {
    const variableCost = litres * PRICING.ratePerLitre;
    return includeDailyFixed ? variableCost + PRICING.dailyFixedCharge : variableCost;
}
```

**Why calculate in JavaScript?**

The API returns *usage in litres*. The dashboard converts to costs because:
- Pricing changes over time (easier to update in one place)
- Different views might calculate costs differently
- Keeps the API focused on raw data

### Rendering Charts with Chart.js

Chart.js is a library that draws beautiful charts on `<canvas>` elements:

```javascript
function renderDailyChart(data) {
    const ctx = document.getElementById('daily-chart').getContext('2d');

    // Sort data by date
    const sortedData = [...data].sort((a, b) =>
        new Date(a.date) - new Date(b.date)
    );

    const labels = sortedData.map(d => d.date);
    const values = sortedData.map(d => d.usage_litres);
    const threshold = 800;

    // Destroy old chart if it exists
    if (dailyChart) {
        dailyChart.destroy();
    }

    // Create new chart
    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Daily Usage (L)',
                data: values,
                backgroundColor: values.map(v =>
                    v > threshold ? COLORS.danger : COLORS.primary
                )
            }]
        },
        options: { /* ... configuration ... */ }
    });
}
```

**What's happening:**

1. **Get the canvas context** — `getContext('2d')` gives us a 2D drawing context
2. **Prepare the data** — sort by date, extract labels and values
3. **Destroy the old chart** — important! Otherwise old charts stack on top
4. **Create a new Chart** — with type, data, and options

**Conditional colouring:**
```javascript
backgroundColor: values.map(v => v > threshold ? COLORS.danger : COLORS.primary)
```

This makes bars red if they exceed 800L, blue otherwise — visual spike detection!

### Event Listeners

Event listeners respond to user interactions:

```javascript
function setupEventListeners() {
    // Range buttons for daily chart (30/90/365 days)
    document.querySelectorAll('.chart-controls .btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            // Remove 'active' class from all buttons
            document.querySelectorAll('.chart-controls .btn')
                .forEach(b => b.classList.remove('active'));
            // Add 'active' class to clicked button
            e.target.classList.add('active');
            // Reload chart with new range
            await loadDailyData(parseInt(e.target.dataset.range));
        });
    });

    // Hourly date picker
    document.getElementById('hourly-date').addEventListener('change', async (e) => {
        await loadHourlyData(e.target.value);
    });
}
```

**Breaking it down:**

1. `querySelectorAll()` — finds all elements matching a CSS selector
2. `forEach()` — loops through each button
3. `addEventListener('click', ...)` — "When this is clicked, run this function"
4. `e.target` — the element that was clicked
5. `classList.add/remove` — adds or removes CSS classes (for styling the active button)
6. `dataset.range` — reads the `data-range` attribute from the HTML

### Auto-Refresh

The dashboard refreshes automatically every 5 minutes:

```javascript
// In initDashboard:
setInterval(refreshData, 5 * 60 * 1000);  // 5 minutes in milliseconds

async function refreshData() {
    console.log('Refreshing data...');
    await Promise.all([
        checkHealth(),
        loadSummary(),
        loadAlerts()
    ]);
}
```

`setInterval(function, milliseconds)` calls a function repeatedly at the specified interval.

### How the Dashboard Connects to the Backend

Here's the complete picture:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                                  │
│                                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                    │
│  │  index.html │   │ styles.css  │   │dashboard.js │                    │
│  │  (Structure)│   │ (Appearance)│   │ (Behaviour) │                    │
│  └─────────────┘   └─────────────┘   └──────┬──────┘                    │
│                                             │                           │
│                                   fetch() requests                      │
│                                             │                           │
└─────────────────────────────────────────────┼───────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI SERVER                                 │
│                                                                         │
│   /api/usage/summary    /api/usage/daily    /api/alerts                 │
│   /api/usage/hourly     /api/usage/monthly  /health                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          SQLITE DATABASE                                │
│                                                                         │
│   daily_usage    hourly_usage    alerts    sync_log                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Real-World Analogy

Think of the dashboard like a **car's dashboard**:

| Car Dashboard | Water Dashboard |
|---------------|-----------------|
| Speedometer needle | Usage numbers in cards |
| Fuel gauge | Charts showing trends |
| Warning lights | Alert section with ⚠️ icons |
| Instrument cluster styling | CSS making it look nice |
| Computer reading sensors | JavaScript fetching from API |

The car's computer constantly reads from sensors and updates the display. Our JavaScript constantly reads from the API and updates the page.

### Key Frontend Concepts Summary

| Concept | What It Does | Example |
|---------|--------------|---------|
| `document.getElementById()` | Finds an element by its ID | Find the "today-usage" div |
| `element.textContent` | Sets the text inside an element | Display "542" litres |
| `fetch()` | Makes HTTP requests to the API | Get usage summary |
| `async/await` | Handles asynchronous operations | Wait for API response |
| `addEventListener()` | Responds to user actions | Handle button clicks |
| `Chart.js` | Draws graphs on canvas | Render bar charts |
| CSS variables | Reusable colour values | `--primary-color` |
| Media queries | Responsive design | Smaller text on mobile |

### Comprehension Check

1. What does `document.getElementById('today-usage')` return?
2. Why do we use `Promise.all()` when loading data in `initDashboard()`?
3. What would happen if we forgot to call `dailyChart.destroy()` before creating a new chart?
4. Why are costs calculated in JavaScript rather than returned by the API?
5. What triggers the `change` event on the hourly date picker?
6. How does the dashboard know to make a bar red instead of blue?

---

## Lesson 11: Putting It All Together

Congratulations! You've learned all the major components. Let's see how they work together.

### The Complete System Flow

Here's what happens from the moment the service starts to when you see data on the dashboard:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           STARTUP (main.py)                             │
│                                                                         │
│  1. Load configuration from .env                                        │
│  2. Connect to SQLite database                                          │
│  3. Start APScheduler with jobs                                         │
│  4. Start FastAPI web server on port 8096                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SCHEDULED JOBS                                  │
│                                                                         │
│  Daily (6 AM):                      Weekly (Sunday 7 AM):               │
│  ┌─────────────────────────┐        ┌─────────────────────────┐         │
│  │ 1. Start Chrome         │        │ 1. Get week's records   │         │
│  │ 2. Login to Thames Water│        │ 2. Compare with meters  │         │
│  │ 3. Navigate to usage    │        │ 3. Flag discrepancies   │         │
│  │ 4. Select dropdowns     │        │ 4. Update verified flag │         │
│  │ 5. Capture network data │        └─────────────────────────┘         │
│  │ 6. Parse JSON response  │                                            │
│  │ 7. Store in database    │                                            │
│  │ 8. Check for spikes     │                                            │
│  │ 9. Send alerts if needed│                                            │
│  │ 10. Close browser       │                                            │
│  └─────────────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATABASE                                      │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ daily_usage  │  │ hourly_usage │  │   alerts     │  │  sync_log    │ │
│  │              │  │              │  │              │  │              │ │
│  │ date         │  │ date         │  │ alert_type   │  │ sync_type    │ │
│  │ usage_litres │  │ hour         │  │ alert_date   │  │ status       │ │
│  │ meter_reading│  │ usage_litres │  │ message      │  │ records      │ │
│  │ verified     │  │ meter_reading│  │ notified     │  │ duration     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              API                                        │
│                                                                         │
│  GET /api/usage/daily    →  Returns daily records as JSON               │
│  GET /api/usage/hourly   →  Returns hourly records for a date           │
│  GET /api/usage/summary  →  Returns calculated statistics               │
│  GET /api/alerts         →  Returns alert history                       │
│  POST /api/sync/trigger  →  Manually triggers a sync (requires API key) │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DASHBOARD                                     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Usage Cards          Cost Cards           Charts               │    │
│  │  ┌──────┐ ┌─────┐     ┌─────┐ ┌─────┐     ┌──────────────────┐  │    │
│  │  │Latest│ │7-Day│     │Daily│ │Month│     │   Daily Usage    │  │    │
│  │  │ Day  │ │ Avg │     │Cost │ │ Est │     │   Bar Chart      │  │    │
│  │  └──────┘ └─────┘     └─────┘ └─────┘     └──────────────────┘  │    │
│  │                                                                 │    │
│  │  ┌──────────────────┐    ┌──────────────────┐                   │    │
│  │  │  Hourly Chart    │    │  Monthly Chart   │                   │    │
│  │  │  (per day)       │    │  (comparison)    │                   │    │
│  │  └──────────────────┘    └──────────────────┘                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Patterns You've Learned

Throughout this codebase, you've seen several patterns that appear in professional Python code:

#### 1. The Singleton Pattern
Used for database and scheduler — ensure only one instance exists.

```python
_db: Database | None = None

def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
```

#### 2. The Repository Pattern
Database queries are in a separate file (`queries.py`), not scattered throughout the code.

```python
# Other code doesn't write SQL directly — it calls these functions
await insert_daily_usage(record)
await get_daily_usage(start_date, end_date)
```

#### 3. The Configuration Pattern
All settings in one place, loaded from environment variables.

```python
settings = get_settings()
threshold = settings.spike_threshold
```

#### 4. Try/Finally for Cleanup
Ensure resources are released even if errors occur.

```python
try:
    self.driver = self._setup_driver()
    # ... do work ...
finally:
    if self.driver:
        self.driver.quit()
```

#### 5. Async/Await for Concurrency
Non-blocking operations allow the server to handle multiple requests.

```python
async def get_daily_usage(...):
    result = await db.fetch_all(query)
    return result
```

#### 6. Dependency Injection
FastAPI's `Depends()` injects functionality into endpoints.

```python
@router.post("/sync/trigger")
async def trigger_sync(api_key: str = Depends(verify_api_key)):
    # api_key is validated before this code runs
```

### The Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Web Framework | FastAPI | Handle HTTP requests, serve API |
| Web Scraping | Selenium + Chrome | Automate browser to extract data |
| Database | SQLite + aiosqlite | Store data persistently |
| Scheduling | APScheduler | Run jobs at specific times |
| Data Validation | Pydantic | Ensure data has correct types |
| Configuration | pydantic-settings | Load settings from environment |
| Dashboard | HTML + Chart.js | Visualise data |

### What Makes This a Good Codebase?

1. **Separation of Concerns** — Each module has one job
2. **Configuration Externalized** — No hardcoded passwords
3. **Error Handling** — Failures are logged and notified
4. **Data Validation** — Pydantic catches invalid data early
5. **Logging** — You can see what happened and when
6. **Auditing** — Sync logs track every operation
7. **Documentation** — API docs are auto-generated

### Where To Go From Here

Now that you understand the codebase, you could:

1. **Add new features:**
   - Cost predictions based on historical trends
   - Comparison with previous year
   - Leak detection algorithms

2. **Improve reliability:**
   - Add retry logic to the scraper
   - Set up monitoring/alerting for failed syncs
   - Add database backups

3. **Learn more about the technologies:**
   - FastAPI documentation: https://fastapi.tiangolo.com/
   - Selenium documentation: https://selenium-python.readthedocs.io/
   - Pydantic documentation: https://docs.pydantic.dev/

### Final Comprehension Check

1. What happens when the application starts? (List the startup sequence)
2. Trace the journey of water usage data from Thames Water's website to the dashboard.
3. Why is the singleton pattern useful for the database connection?
4. What would happen if the scraper's `finally` block didn't close the browser?
5. How does the dashboard know when to refresh its data?

---

## Glossary

| Term | Definition |
|------|------------|
| **API** | Application Programming Interface — a way for programs to communicate |
| **async/await** | Python syntax for non-blocking (concurrent) code |
| **CRUD** | Create, Read, Update, Delete — basic database operations |
| **Decorator** | `@something` — modifies a function's behavior |
| **Endpoint** | A specific URL that handles requests |
| **FastAPI** | A modern Python web framework |
| **Headless** | Running a browser without a visible window |
| **JSON** | JavaScript Object Notation — a data format |
| **Pydantic** | A Python library for data validation |
| **REST** | A standard architecture for web APIs |
| **Scheduler** | Code that runs tasks at specific times |
| **Scraping** | Extracting data from websites programmatically |
| **Selenium** | A tool for controlling web browsers |
| **Singleton** | A pattern ensuring only one instance of something exists |
| **SQL** | Structured Query Language — for database operations |
| **SQLite** | A simple file-based database |
| **Upsert** | Insert if new, update if exists |

---

*Tutorial complete! You now have a solid understanding of how this Thames Water monitoring service works. If you have questions about any specific part, refer back to the relevant lesson.*
