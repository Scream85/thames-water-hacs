"""API middleware for authentication and logging."""

import hmac

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
ingest_key_header = APIKeyHeader(name="X-Ingest-Key", auto_error=False)


async def verify_ingest_key(
    ingest_key: str | None = Security(ingest_key_header),
) -> str:
    """Authenticate Hands independently from the service's administrative API key."""
    expected = get_settings().ingest_api_key
    if not ingest_key:
        raise HTTPException(status_code=401, detail="Missing ingest key")
    if not expected or not hmac.compare_digest(ingest_key, expected):
        raise HTTPException(status_code=403, detail="Invalid ingest key")
    return ingest_key


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """
    Verify API key for protected endpoints.

    Args:
        request: FastAPI request object
        api_key: API key from header

    Returns:
        API key if valid

    Raises:
        HTTPException: If API key is invalid
    """
    settings = get_settings()

    # Skip auth for health endpoint and dashboard
    if request.url.path in ["/health", "/", "/favicon.ico"]:
        return None

    # Skip auth for GET requests on public endpoints
    public_paths = [
        "/api/usage/summary",
        "/api/usage/daily",
        "/api/usage/hourly",
        "/api/usage/monthly",
        "/api/alerts",
    ]

    if request.method == "GET" and request.url.path in public_paths:
        # Allow read access without API key for now
        # In production, you may want to require auth for all endpoints
        return None

    # Require auth for POST/PUT/DELETE and admin endpoints
    if request.url.path.startswith("/api/sync") or request.method in ["POST", "PUT", "DELETE"]:
        if not api_key:
            logger.warning(
                "Missing API key for protected endpoint",
                extra={"path": request.url.path, "method": request.method}
            )
            raise HTTPException(
                status_code=401,
                detail="Missing API key"
            )

        if api_key != settings.thames_water_api_key:
            logger.warning(
                "Invalid API key",
                extra={"path": request.url.path}
            )
            raise HTTPException(
                status_code=403,
                detail="Invalid API key"
            )

    return api_key


async def log_request(request: Request) -> None:
    """Log incoming request."""
    logger.info(
        "Incoming request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
        }
    )
