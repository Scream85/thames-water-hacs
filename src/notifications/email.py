"""Email notification functionality."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def send_alert_email(subject: str, body: str) -> bool:
    """
    Send an alert email notification.

    Args:
        subject: Email subject
        body: Email body text

    Returns:
        True if sent successfully, False otherwise
    """
    settings = get_settings()

    if not settings.notification_email:
        logger.warning("No notification email configured, skipping alert")
        return False

    if not settings.smtp_host:
        logger.warning("SMTP not configured, logging alert instead")
        logger.info(f"ALERT: {subject}\n{body}")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_from or settings.notification_email
        msg["To"] = settings.notification_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)

        logger.info(f"Alert email sent: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
        return False


async def send_error_notification(
    error_type: str,
    error_message: str,
    date: str | None = None,
) -> bool:
    """
    Send an error notification email.

    Args:
        error_type: Type of error (e.g., "Sync Failed", "Scraper Error")
        error_message: Detailed error message
        date: Optional date context

    Returns:
        True if sent successfully, False otherwise
    """
    subject = f"Thames Water Service Error: {error_type}"

    body = f"""
Thames Water Monitoring Service Error

Error Type: {error_type}
{"Date: " + date if date else ""}
Time: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Error Details:
{error_message}

---
This is an automated notification from the Thames Water Monitoring Service.
Please check the service logs for more details.

Service URL: {settings.service_url}
    """.strip()

    return await send_alert_email(subject, body)


async def send_daily_summary(
    date: str,
    usage_litres: float,
    average_litres: float,
    trend: str,
) -> bool:
    """
    Send a daily usage summary email.

    Args:
        date: Date of the summary
        usage_litres: Total usage for the day
        average_litres: Average daily usage
        trend: Usage trend indicator

    Returns:
        True if sent successfully, False otherwise
    """
    settings = get_settings()

    # Only send if usage is notable (above threshold or significant change)
    if usage_litres < settings.spike_threshold * 0.8:
        return False

    subject = f"Thames Water Daily Summary: {date}"

    trend_emoji = "📈" if trend == "up" else "📉" if trend == "down" else "➡️"

    body = f"""
Thames Water Daily Usage Summary

Date: {date}
Usage: {usage_litres:.0f} litres
Average: {average_litres:.1f} litres
Trend: {trend_emoji} {trend}

{"⚠️ Warning: Usage approaching threshold!" if usage_litres > settings.spike_threshold * 0.8 else ""}

---
View detailed stats: {settings.service_url}
    """.strip()

    return await send_alert_email(subject, body)
