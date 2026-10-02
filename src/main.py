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

# Set up logging first
setup_logging()
logger = get_logger(__name__)


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

    yield

    # Shutdown
    logger.info("Shutting down Thames Water Monitoring Service")

    # Stop scheduler
    try:
        from src.scheduler.manager import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass

    # Disconnect database
    await db.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Thames Water Monitoring Service",
    description="Automated water usage monitoring with REST API and dashboard",
    version="2.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the dashboard HTML."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Thames Water Monitoring Service", "docs": "/docs"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon."""
    favicon_path = static_path / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return None


def main():
    """Run the application."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=False,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
