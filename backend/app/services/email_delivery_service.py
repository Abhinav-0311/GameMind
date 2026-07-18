import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_account_link(email: str, subject: str, path: str, token: str) -> None:
    """Deliver account links through configured SMTP; disabled mode is local-development only."""
    link = f"{settings.PUBLIC_APP_URL.rstrip('/')}{path}?token={token}"
    if settings.EMAIL_DELIVERY_MODE == "disabled":
        logger.info("Email delivery disabled for %s. Account link: %s", email, link)
        return
    if settings.EMAIL_DELIVERY_MODE != "smtp":
        raise RuntimeError("Unsupported EMAIL_DELIVERY_MODE")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM_ADDRESS
    message["To"] = email
    message.set_content(f"{subject}\n\nOpen this link: {link}\n")
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
        if settings.SMTP_USE_TLS:
            client.starttls()
        if settings.SMTP_USERNAME:
            client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        client.send_message(message)
