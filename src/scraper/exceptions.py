"""Custom exceptions for Thames Water scraper."""


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class LoginError(ScraperError):
    """Failed to log into Thames Water."""

    pass


class NavigationError(ScraperError):
    """Failed to navigate to required page."""

    pass


class ExtractionError(ScraperError):
    """Failed to extract data from page."""

    pass


class DataValidationError(ScraperError):
    """Extracted data failed validation."""

    pass


class SessionExpiredError(ScraperError):
    """Login session has expired."""

    pass
