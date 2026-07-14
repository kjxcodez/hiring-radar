"""SMTP outreach email sender layer for hiring-radar.

WARNING:
This module sends real emails on the real behalf of the user.
Every caller in the codebase must gate calls to these functions behind explicit
user confirmation. This module is designed as a direct, simple sender and
does not implement safety confirmation checks itself.
"""

from __future__ import annotations

from email.mime.text import MIMEText
import smtplib
from loguru import logger

from app.config import settings, yaml_config


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send a plain-text email to the recipient using the configured SMTP server.

    Args:
        to_address: Recipient email address.
        subject: Email subject line.
        body: Email plain text body content.

    Returns:
        True if the email was sent successfully, False otherwise.

    Raises:
        RuntimeError: If SMTP username or SMTP app password settings are not configured.
    """
    # Verify SMTP credentials
    if not settings.smtp_username or not settings.smtp_app_password:
        missing = []
        if not settings.smtp_username:
            missing.append("SMTP_USERNAME")
        if not settings.smtp_app_password:
            missing.append("SMTP_APP_PASSWORD")
        raise RuntimeError(
            f"SMTP configuration is incomplete. Please set the following keys in your .env file: "
            f"{', '.join(missing)}"
        )

    # Build plain-text MIME message
    msg = MIMEText(body, "plain", "utf-8")
    from_name = yaml_config.email.from_name or "Kapil Kumar Jangid"
    msg["From"] = f"{from_name} <{settings.smtp_username}>"
    msg["To"] = to_address
    msg["Subject"] = subject

    # Connect and send
    logger.debug("Attempting to connect to SMTP server {host}:{port}...", host=settings.smtp_host, port=settings.smtp_port)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_app_password)
            server.send_message(msg)

        logger.info("Successfully sent outreach email to '{recipient}'", recipient=to_address)
        return True

    except Exception as exc:
        # Log failure at ERROR level. NEVER include the smtp_app_password in the log message.
        logger.error(
            "Failed to send outreach email to '{recipient}' via {host}:{port} — {exc}",
            recipient=to_address,
            host=settings.smtp_host,
            port=settings.smtp_port,
            exc=exc
        )
        return False


def send_test_email(to_address: str) -> bool:
    """Send a fixed test email to verify that SMTP and Gmail App Password settings work."""
    subject = "Hiring Radar SMTP Connection Test"
    body = (
        "Hello,\n\n"
        "This is a test message from Hiring Radar to confirm that your SMTP "
        "and App Password settings are correctly configured.\n\n"
        "If you received this, everything is working properly!\n\n"
        "Best,\n"
        "Hiring Radar Team"
    )
    return send_email(to_address=to_address, subject=subject, body=body)
